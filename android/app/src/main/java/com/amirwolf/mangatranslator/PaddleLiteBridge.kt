package com.amirwolf.mangatranslator

import android.util.Log
import com.baidu.paddle.lite.MobileConfig
import com.baidu.paddle.lite.PaddlePredictor
import com.baidu.paddle.lite.PowerMode
import java.nio.FloatBuffer
import java.util.concurrent.ConcurrentHashMap

/**
 * v1.14.106 — پلِ Paddle-Lite برای استخراجِ متن (درخواستِ کاربر:
 * «ML Kit خوب استخراج نمی‌زنه؛ Paddle-Lite — هم GPU هم CPU»).
 *
 * پایتون (manga.py → PaddleOCRLiteBackend) پیش/پس‌پردازش را انجام می‌دهد و
 * فقط «تانسور» را می‌فرستد؛ این پل فقط inference است:
 *   predict(path, shape, floatData) → FloatBuffer خروجی
 *   predictShape(path)              → شکلِ خروجیِ آخرِ همان مدل
 *   ready(path)                     → ساختِ موفقِ predictor؟
 *   backend(path)                   → نامِ بکاندِ شتاب ("opencl") یا ""
 *
 * مدل‌ها .nb هستند (تبدیل‌شده با opt و valid_targets="arm opencl" — سازگار
 * با armv7 و armv8 هر دو)؛ کتابخانهٔ libpaddle_lite_jni.so از بیلدِ opencl
 * است (هر دو ABI از v1.14.109) → کرنل‌های OpenCL گوشی برای همهٔ OPهایِ
 * پشتیبانی‌شده فعال می‌شود و بقیه رویِ ARM CPU.
 */
object PaddleLiteBridge {

    private const val TAG = "PaddleLiteBridge"

    // v1.14.109 — لودِ صریحِ امن: اگر .so برایِ ABIِ گوشی نباشد (بیلدِ
    // arm64-only رویِ گوشیِ ۳۲-بیتی یا jar بدونِ so) به‌جایِ
    // UnsatisfiedLinkError داخلِ initِ کلاسِ paddle، همین‌جا یک بار
    // مدیریت می‌شود → ready()=false → پایتون می‌رود سراغِ ML Kit.
    @Volatile
    private var libState: Int = -1 // 1=لود شد، 0=نبود/نشد، -1=هنوز نه

    private fun ensureLib(): Boolean {
        when (libState) {
            1 -> return true
            0 -> return false
        }
        return try {
            System.loadLibrary("paddle_lite_jni")
            libState = 1
            Log.i(TAG, "libpaddle_lite_jni loaded (opencl build)")
            true
        } catch (t: Throwable) {
            libState = 0
            Log.e(TAG, "libpaddle_lite_jni load failed — paddle off, "
                    + "ML Kit fallback: " + t.message)
            false
        }
    }

    /** وضعیتِ کتابخانهٔ بومی — برایِ لاگ/دیباگ */
    @JvmStatic
    fun libOk(): Boolean = ensureLib()

    // کشِ predictor per-model — det و rec هرکدام یک مسیر
    private val predictors = ConcurrentHashMap<String, PaddlePredictor>()
    private val building = ConcurrentHashMap<String, Any>()
    private val lastOutShape = ConcurrentHashMap<String, LongArray>()

    /** نامِ فایلِ کتابخانهٔ بومی — تستِ آماده‌بودن بدونِ ساختِ مدل */
    @JvmStatic
    fun libName(): String = "libpaddle_lite_jni.so"

    @Synchronized
    private fun getOrCreate(modelPath: String, threads: Int): PaddlePredictor? {
        if (!ensureLib()) return null
        predictors[modelPath]?.let { return it }
        // ساختِ همزمانِ دوباره را جلوگیری کن (قفلِ ساده per-path)
        synchronized(building.getOrPut(modelPath) { Any() }) {
            predictors[modelPath]?.let { return it }
            return try {
                val cfg = MobileConfig()
                cfg.setModelFromFile(modelPath)
                cfg.threads = if (threads in 1..8) threads else 4
                cfg.powerMode = PowerMode.LITE_POWER_HIGH
                val p = PaddlePredictor.createPaddlePredictor(cfg)
                if (p != null) {
                    predictors[modelPath] = p
                    Log.i(TAG, "predictor ready: $modelPath (threads=$threads)")
                } else {
                    Log.e(TAG, "createPaddlePredictor returned null: $modelPath")
                }
                p
            } catch (t: Throwable) {
                Log.e(TAG, "createPaddlePredictor failed: $modelPath", t)
                null
            }
        }
    }

    /** آیا این مدل می‌تواند ساخته شود؟ (بدونِ اجرا) */
    @JvmStatic
    fun ready(modelPath: String, threads: Int = 4): Boolean =
        getOrCreate(modelPath, threads) != null

    /** بکاندِ شتابِ این کتابخانه — برایِ لاگِ پایتون (خالی = لود نشده) */
    @JvmStatic
    fun backend(modelPath: String): String =
        if (ensureLib()) "opencl" else ""

    /**
     * یک بارِ inference: ورودیِ float با شکلِ [shape] → خروجی به‌صورت
     * FloatBuffer (پایتون با memoryview می‌خواند — بدونِ کپیِ عنصری).
     * shape: LongArray؛ data: FloatArray (از پایتون jfloat[] می‌آید).
     */
    @JvmStatic
    fun predict(modelPath: String, shape: LongArray, data: FloatArray,
                threads: Int = 4): FloatBuffer? {
        if (!ensureLib()) return null
        val p = getOrCreate(modelPath, threads) ?: return null
        return try {
            val input = p.getInput(0) ?: return null
            if (!input.resize(shape)) return null
            if (!input.setData(data)) return null
            if (!p.run()) return null
            val out = p.getOutput(0) ?: return null
            val shp = out.shape()
            if (shp != null) lastOutShape[modelPath] = shp
            val arr = out.floatData ?: return null
            FloatBuffer.wrap(arr)
        } catch (t: Throwable) {
            Log.e(TAG, "predict failed: $modelPath", t)
            null
        }
    }

    /** شکلِ خروجیِ آخرِ predict برایِ همین مدل (برای reshape در پایتون) */
    @JvmStatic
    fun predictShape(modelPath: String): LongArray? = lastOutShape[modelPath]

    /** آزادسازی — فعلاً predictorها تا پایانِ پروسه کش می‌مانند */
    @JvmStatic
    fun releaseAll() {
        predictors.clear()
        lastOutShape.clear()
    }
}
