plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.amirwolf.mangatranslator"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.amirwolf.mangatranslator"
        minSdk = 24
        targetSdk = 34
        versionCode = 84
        versionName = "1.14.70"

        val buildAbis = ((findProperty("appAbis") as String?)
            ?: "arm64-v8a,armeabi-v7a")
            .split(",").map { it.trim() }.filter { it.isNotEmpty() }
        ndk {
            abiFilters += buildAbis
        }

    }

    packaging {
        // v1.14.67 — رویِ امولاتورِ x86_64 (ترجمهٔ arm64) لودِ .soِ
        // فشرده‌نشده از داخلِ APK ممکن است کار نکند → با -PlegacyJni=true
        // کتابخانه‌ها extract می‌شوند (فقط برایِ تستِ CI؛ پیش‌فرض false)
        jniLibs.useLegacyPackaging =
            ((findProperty("legacyJni") as String?) == "true")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}


val engineRoot = rootProject.projectDir.parentFile
tasks.register<Copy>("copyEngineSources") {
    from(engineRoot) { include("manga.py", "manga_app.py") }
    into("src/main/assets/engine")
}
tasks.named("preBuild") { dependsOn("copyEngineSources") }


chaquopy {
    sourceSets {
        getByName("main") {
            exclude("rapidocr/models/*.onnx")
            exclude("rapidocr/models/*.onnx.*")
            exclude("**/__pycache__/**")
        }
    }
    defaultConfig {
        version = "3.10"
        buildPython = listOf(
            (findProperty("chaquopyBuildPython") as String?) ?: "python3")
        pip {
            install("numpy==1.26.2")
            install("opencv-python==4.5.1.48")
            install("pillow")
            install("shapely")
            install("arabic-reshaper")
            install("python-bidi==0.4.2")
            install("pyyaml")
            install("requests")
            install("six")
            install("tqdm")
            install("omegaconf")
            install("colorlog")
        }
    }
}

// v1.14.108 — اگر fetch_paddle اجرا نشده باشد (jar غایب): PaddleLiteBridge.kt
// موقتاً به ‎.off منتقل می‌شود تا بدونِ کلاس‌های com.baidu.paddle.lite کامپایل سالم بماند
// v1.14.108 — اگر fetch_paddle اجرا نشده باشد (jar غایب):
// وابستگی و PaddleLiteBridge.kt از کامپایل حذف می‌شوند تا بیلد
// نشکند؛ runtime jclass نمی‌یابد → پایتون به ONNX/ML Kit می‌رود.
val paddleJar = file("libs/PaddlePredictor.jar")
val hasPaddle = paddleJar.exists() && paddleJar.length() > 0
if (!hasPaddle) {
    logger.lifecycle("PaddlePredictor.jar missing -> Paddle-Lite disabled (ML Kit fallback)")
}

val paddleBridgeKt = file("src/main/java/com/amirwolf/mangatranslator/PaddleLiteBridge.kt")
val paddleBridgeOff = file("src/main/java/com/amirwolf/mangatranslator/PaddleLiteBridge.kt.off")
if (!hasPaddle && paddleBridgeKt.exists()) {
    paddleBridgeKt.renameTo(paddleBridgeOff)
}
if (hasPaddle && paddleBridgeOff.exists()) {
    paddleBridgeOff.renameTo(paddleBridgeKt)
}


dependencies {
    // v1.14.67 — ortVer برایِ CIِ امولاتور: AARِ 1.31 رویِ x86_64 در
    // sess.run تقسیم‌برصفر (SIGFPE) می‌دهد → CI با 1.28 بیلد می‌کند
    // (APIِ جاوایِ shim با 1.28 هم سازگار است؛ گوشی همان 1.31 را می‌گیرد)
    implementation("com.microsoft.onnxruntime:onnxruntime-android:${(findProperty("ortVer") as String?) ?: "1.31.0"}")
    // v1.14.106 — Paddle-Lite (استخراجِ متن با OpenCL گوشی + CPU) —
    // jar و so قبل از بیلد با «python3 android/scripts/fetch_paddle.py»
    // دانلود می‌شوند (CI خودش انجام می‌دهد)
    if (hasPaddle) {
        implementation(files(paddleJar))
    }
    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.mlkit:text-recognition-japanese:16.0.1")
    implementation("com.google.mlkit:text-recognition-korean:16.0.1")
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("com.google.android.material:material:1.12.0")
}
