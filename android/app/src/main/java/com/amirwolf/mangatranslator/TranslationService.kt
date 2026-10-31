package com.amirwolf.mangatranslator

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

// v1.14.150 — سرویسِ پیشزمینهٔ ترجمه: تا وقتی کاری در جریان است، اپ را
// از فریزِ «پردازهٔ انبارشده» (cached-app freezer، اندروید ۱۱+) در امان
// نگه میدارد. کاربر میرود سراغِ اپِ دیگر، استخراج/پاکسازی/ترجمه ادامه
// پیدا میکند. کنترل از MainActivity: شروع با acquireKeepAwake (شروعِ
// کار)، توقف با releaseKeepAwake (پایانِ کار).
class TranslationService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        try {
            goForeground()
        } catch (_: Exception) {
            try {
                stopSelf()
            } catch (_: Exception) {
            }
        }
        return START_STICKY
    }

    private fun goForeground() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(
                NotificationChannel(
                    CH_ID, "ترجمه در جریان",
                    NotificationManager.IMPORTANCE_LOW
                )
            )
        }
        val b = if (Build.VERSION.SDK_INT >= 26) {
            Notification.Builder(this, CH_ID)
        } else {
            @Suppress("DEPRECATION") Notification.Builder(this)
        }
        b.setContentTitle("مانگا مترجم")
            .setContentText("در حال ترجمه… میتوانید بروید سراغ اپهای دیگر؛ کار ادامه پیدا میکند")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
        val n = b.build()
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(
                NOTIF_ID, n,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            @Suppress("DEPRECATION")
            startForeground(NOTIF_ID, n)
        }
    }

    companion object {
        private const val CH_ID = "translation"
        private const val NOTIF_ID = 4150
    }
}
