package com.amirwolf.mangatranslator

import android.app.Service
import android.content.Intent
import android.os.IBinder
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OnnxValue
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.nio.FloatBuffer

/**
 * v1.14.156 — پروبِ شتابدهندههایِ ORT در پروسهٔ جدا (:epprobe).
 *
 * ریشهٔ کرشِ 1.14.155 (سیگ‌فالتِ faulthandler در onnxruntime/__init__.py
 * run → rapidocr_mobile._open): XNNPACK EP رویِ بعضی مدلها/گوشیها (اینجا:
 * PP-OCRv6 medium رویِ Poco F4 / SD870) در اجرایِ نیتیو سیگ‌فالت میزند —
 * گیرفتنِ سیگ‌فالت در پروسهٔ اصلیِ پایتون غیرممکن است (try/except فقط
 * ORT_FAIL را میگیرد) → اپ موقعِ ساختِ اولین سشنِ OCR میمرد.
 *
 * درمان: بنچمارک + چکِ صحتِ خروجیِ XNNPACK/NNAPI فقط همینجا (پروسهٔ
 * :epprobe) با Java API واقعیِ onnxruntime-android اجرا میشود —
 * سیگ‌فالت فقط این پروسه را میکشد و اپِ اصلی دستنخورده میماند.
 * پایتون (rapidocr_mobile) نتیجه را از فایلِ «out» میخواند:
 *   «verdict ok <ms>»  = EP سالم و این سریعیت را دارد
 *   «verdict fail …»  = خطایِ پایتونی/جا (مثلاً مدل باز نشد)
 *   فایلِ غایب            = کرشِ نیتیو (سیگ‌فالت) یا تایم‌اوت → EP مردود
 *
 * ترتیبِ بنچ: det با دو شکلِ واقعی (64² و 512² — شکلِ عوضشده هم پوشش
 * داده شود) + rec با 48×320. خروجیِ EP با خروجیِ سشنِ CPUِ مرجع سنجیده
 * میشود (NaN/بی‌نهایت یا اختلافِ نسبیِ > 0.15 = EP درست حساب نمیزند →
 * مردود). بعدِ تمام، پروسه با killProcess بسته میشود تا رمِ مدلهایِ
 * ۵۹+۷۳MB آزاد بماند.
 */
class EpProbeService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val detPath = intent?.getStringExtra("det") ?: ""
        val recPath = intent?.getStringExtra("rec") ?: ""
        val ep = (intent?.getStringExtra("ep") ?: "xnnpack").lowercase()
        val outPath = intent?.getStringExtra("out") ?: ""
        val xnnThreads = intent?.getStringExtra("threads") ?: "4"
        Thread {
            val sb = StringBuilder()
            try {
                probeAll(detPath, recPath, ep, xnnThreads, sb)
            } catch (t: Throwable) {
                android.util.Log.e("EpProbe", "probe $ep failed", t)
                sb.append("verdict fail ").append(t.javaClass.simpleName)
                    .append(": ").append(t.message?.take(140) ?: "").append("\n")
            }
            try {
                if (outPath.isNotEmpty()) {
                    java.io.File(outPath).writeText(sb.toString())
                }
            } catch (_: Exception) { }
            try { stopSelf() } catch (_: Exception) { }
            try {
                android.os.Process.killProcess(android.os.Process.myPid())
            } catch (_: Exception) { }
        }.start()
        return START_NOT_STICKY
    }

    private fun cpuOpts(): OrtSession.SessionOptions {
        val so = OrtSession.SessionOptions()
        so.setIntraOpNumThreads(2)
        so.setMemoryPatternOptimization(false)
        so.setCPUArenaAllocator(false)
        return so
    }

    private fun epOpts(ep: String, xnnThreads: String): OrtSession.SessionOptions {
        val so = OrtSession.SessionOptions()
        when (ep) {
            "nnapi" -> {
                // نیازمندیهایِ مستندِ NNAPI EP (شکلِ داینامیک): mem pattern
                // خاموش + arena خاموش — نبودشان خودش منبعِ کرش/خرابی است.
                so.addNnapi()
                so.setMemoryPatternOptimization(false)
                so.setCPUArenaAllocator(false)
            }
            else -> {
                // کانفیگِ رسمیِ XNNPACK: ORT intra=1 + spinning خاموش +
                // threadpoolِ XNNPACK = هستههایِ سریع.
                so.setIntraOpNumThreads(1)
                so.addConfigEntry("session.intra_op.allow_spinning", "0")
                val m = java.util.HashMap<String, String>()
                m["intra_op_num_threads"] = xnnThreads
                so.addXnnpack(m)
            }
        }
        return so
    }

    private fun probeAll(
        detPath: String, recPath: String, ep: String,
        xnnThreads: String, sb: StringBuilder
    ) {
        val env = OrtEnvironment.getEnvironment()
        val total = benchModel(env, detPath, ep, xnnThreads, true, sb)
        val totalRec = benchModel(env, recPath, ep, xnnThreads, false, sb)
        sb.append("verdict ok ").append(total + totalRec).append("\n")
    }

    /** بنچِ یک مدل: سشنِ مرجعِ CPU + سشنِ EP؛ برایِ هر شکل دو run (بهترینِ
     *  زمان) + مقایسهٔ خروجی با CPU. خطا/ناسازگاری → exception → verdict fail. */
    private fun benchModel(
        env: OrtEnvironment, path: String, ep: String, xnnThreads: String,
        isDet: Boolean, sb: StringBuilder
    ): Double {
        val ref = env.createSession(path, cpuOpts())
        val eps = env.createSession(path, epOpts(ep, xnnThreads))
        try {
            val inName = eps.inputNames.iterator().next()
            val outName = eps.outputNames.iterator().next()
            val shapes = if (isDet) arrayOf(
                longArrayOf(1, 3, 64, 64), longArrayOf(1, 3, 512, 512)
            ) else arrayOf(longArrayOf(1, 3, 48, 320))
            var sum = 0.0
            for (sh in shapes) {
                val n = sh.fold(1L) { a, b -> a * b }.toInt()
                val data = FloatArray(n)
                // ورودیِ غیرصفرِ کوچک تا مسیرِ عددیِ واقعی هم برود (نه همهٔ صفر)
                for (i in data.indices) data[i] = ((i * 37) % 255) / 255f - 0.5f
                val t = OnnxTensor.createTensor(env, FloatBuffer.wrap(data), sh)
                var best = Double.MAX_VALUE
                var lastOut: OnnxTensor? = null
                try {
                    for (i in 0..1) {
                        val inputs = java.util.LinkedHashMap<String, OnnxValue>()
                        inputs[inName] = t
                        val t0 = System.nanoTime()
                        val res = eps.run(inputs)
                        val ms = (System.nanoTime() - t0) / 1e6
                        if (i == 1) lastOut = res.get(0) as OnnxTensor
                        else res.close()
                        if (ms < best) best = ms
                    }
                    val inputs = java.util.LinkedHashMap<String, OnnxValue>()
                    inputs[inName] = t
                    val refRes = ref.run(inputs)
                    val refT = refRes.get(0) as OnnxTensor
                    val rel = try {
                        maxRelDiff(lastOut!!.floatBuffer, refT.floatBuffer)
                    } finally {
                        try { refRes.close() } catch (_: Exception) { }
                    }
                    if (rel > 0.15) {
                        throw RuntimeException(
                            "خروجیِ $ep با CPU نمیخواند (rel=$rel, tag=$outName)")
                    }
                    sb.append(if (isDet) "det " else "rec ")
                        .append(sh[3]).append(" ok ").append(best).append("\n")
                    sum += best
                } finally {
                    try { t.close() } catch (_: Exception) { }
                    try { lastOut?.close() } catch (_: Exception) { }
                }
            }
            return sum
        } finally {
            try { eps.close() } catch (_: Exception) { }
            try { ref.close() } catch (_: Exception) { }
        }
    }

    private fun maxRelDiff(a: FloatBuffer, b: FloatBuffer): Double {
        val n = minOf(a.remaining(), b.remaining())
        var amax = 1e-6
        var dmax = 0.0
        var badA = false
        var badB = false
        for (i in 0 until n) {
            val x = a.get(i)
            val y = b.get(i)
            if (x.isNaN() || x.isInfinite()) badA = true
            if (y.isNaN() || y.isInfinite()) badB = true
            if (Math.abs(x) > amax) amax = Math.abs(x).toDouble()
            val d = Math.abs(x - y)
            if (d > dmax) dmax = d.toDouble()
        }
        if (badA != badB) return 1e9
        return dmax / amax
    }
}
