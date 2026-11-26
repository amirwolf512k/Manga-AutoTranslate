
package com.paddle.ocr

data class PaddleOCRConfig(
    val detImgMode: String = "BGR",
    val detLimitSideLen: Int = 64,
    val detLimitType: String = "min",
    val detMaxSideLimit: Int = 4000,
    val detThresh: Float = 0.3f,
    val detBoxThresh: Float = 0.6f,
    val detUnclipRatio: Float = 1.5f,
    val detMaxCandidates: Int = 3000,
    val detUseDilation: Boolean = false,
    val detScoreMode: String = "fast",
    val detBoxType: String = "quad",
    // v1.14.509 — پدینگِ سفیدِ دورِ تصویرِ قبل از det — همانِ رفتارِ
    // پیش‌فرضِ RapidOcrAndroidOnnx (padding=50, BORDER_ISOLATED, سفید):
    // متنِ چسبیده به لبهٔ کراپ هم دیده میشود؛ کوordها بعداً پدینگ را کم
    // میکنند و سقفِ بزرگ‌نمایی هم 2*padding اضافه میگیرد تا رزولوشنِ
    // محتوایِ اصلی عوض نشود (main.cpp: resize += 2*padding).
    val detPadding: Int = 50,
    val recScoreThresh: Float = 0.0f,
    val recBatchSize: Int = 1,
)
