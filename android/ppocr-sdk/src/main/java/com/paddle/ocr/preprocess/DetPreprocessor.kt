
package com.paddle.ocr.preprocess

import android.graphics.Bitmap
import com.paddle.ocr.util.BitmapUtils
import com.paddle.ocr.util.ImageUtils
import org.opencv.core.Core
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.core.Scalar
import org.opencv.imgproc.Imgproc

data class DetPreprocessResult(
    val tensorData: FloatArray,
    val shape: LongArray,
    val originalH: Int,
    val originalW: Int,
    // v1.14.509 — پدینگِ سفیدِ RapidOcrAndroidOnnx: originalH/W ابعادِ
    // تصویرِ «پدیده» است؛ DBPostProcessor با کمکردنِ padding کووردها را
    // به فضایِ تصویرِ اصلی برمیگرداند.
    val padding: Int = 0,
)

object DetPreprocessor {
    private val mean = doubleArrayOf(0.485, 0.456, 0.406)
    private val std = doubleArrayOf(0.229, 0.224, 0.225)
    private const val scale = 1.0 / 255.0

    fun preprocess(
        bitmap: Bitmap,
        limitSideLen: Int,
        limitType: String,
        maxSideLimit: Int,
        imgMode: String,
        padding: Int = 0,
    ): DetPreprocessResult {
        val src = BitmapUtils.bitmapToBGRMat(bitmap)
        return try {
            preprocess(src, limitSideLen, limitType, maxSideLimit, imgMode, padding)
        } finally {
            src.release()
        }
    }

    fun preprocess(
        src: Mat,
        limitSideLen: Int,
        limitType: String,
        maxSideLimit: Int,
        imgMode: String,
        padding: Int = 0,
    ): DetPreprocessResult {
        val originalH = src.rows()
        val originalW = src.cols()

        // v1.14.509 — پدینگِ سفید ۵۰px دورِ تصویر قبل از det — همانِ
        // RapidOcrAndroidOnnx (makePadding: BORDER_ISOLATED + سفید).
        // پیادهسازی با Mat+submat+copyTo چون آرتیفکتِ org.opencv:opencv
        // Imgproc.copyMakeBorder ندارد (کلاسِ Imgprocِ آن زیرمجموعه است) —
        // نتیجه بایت‌به‌بایت همانِ BORDER_ISOLATED سفید است: قابِ سفید +
        // تصویرِ دست‌نخورده در مرکز. متنِ لبه‌ای که قبلاً از دیتکتور
        // میگریخت حالا داخلِ قاب میآید.
        var work = src
        var workOwned = false
        val pad = padding.coerceIn(0, 200)
        if (pad > 0) {
            val padded = Mat(originalH + 2 * pad, originalW + 2 * pad,
                src.type(), Scalar(255.0, 255.0, 255.0))
            val roi = padded.submat(pad, pad + originalH, pad, pad + originalW)
            src.copyTo(roi)
            roi.release()
            work = padded
            workOwned = true
        }
        val input = if (imgMode.uppercase() == "RGB") {
            Mat().also { Imgproc.cvtColor(work, it, Imgproc.COLOR_BGR2RGB) }
        } else {
            work
        }

        // main.cpp: resize = maxSideLen + 2*padding — رزولوشنِ محتوایِ
        // اصلی همانِ حالتِ بدونِ پدینگ میماند (پدینگ سهمِ خودش را
        // میگیرد، نه متن).
        val effectiveLimit = if (pad > 0) limitSideLen + 2 * pad else limitSideLen
        var resized = ImageUtils.resizeToMultipleOf32(input, effectiveLimit, limitType, maxSideLimit)
        if (input !== work) input.release()
        val paddedH = if (pad > 0) originalH + 2 * pad else originalH
        val paddedW = if (pad > 0) originalW + 2 * pad else originalW

        val h = resized.rows()
        val w = resized.cols()
        val floatMat = Mat(h, w, CvType.CV_32FC3)
        resized.convertTo(floatMat, CvType.CV_32F)

        val channels = mutableListOf<Mat>()
        Core.split(floatMat, channels)
        for (c in 0..2) {
            Core.multiply(channels[c], Scalar(scale), channels[c])
            Core.subtract(channels[c], Scalar(mean[c]), channels[c])
            Core.divide(channels[c], Scalar(std[c]), channels[c])
        }
        resized.release()
        floatMat.release()

        val channelSize = h * w
        val tensorData = FloatArray(3 * channelSize)
        for (c in 0..2) {
            val chan = channels[c]
            val buf = FloatArray(channelSize)
            chan.get(0, 0, buf)
            System.arraycopy(buf, 0, tensorData, c * channelSize, channelSize)
            chan.release()
        }

        if (workOwned) work.release()

        return DetPreprocessResult(
            tensorData = tensorData,
            shape = longArrayOf(1, 3, h.toLong(), w.toLong()),
            originalH = paddedH,
            originalW = paddedW,
            padding = pad,
        )
    }
}
