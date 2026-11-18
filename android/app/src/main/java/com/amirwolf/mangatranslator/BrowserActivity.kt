package com.amirwolf.mangatranslator

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.CookieManager
import android.webkit.JsResult
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import org.json.JSONArray

class BrowserActivity : Activity() {

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_LINKS = "links"

        var lastSite: String = ""

        private const val EXTRACT_JS = """
(function(){
try{
if(/(^|\.)mangaplus\.shueisha\.co\.jp${'$'}/i.test(location.host)&&location.pathname.indexOf('/viewer/')===0)return [location.href];
}catch(e){}
function abs(u){try{var a=document.createElement('a');a.href=u;return a.href}catch(e){return null}}
function qsz(u){
var m=String(u).match(/[?&](?:type|size|w|h|width|height)=(f?)(\d{1,4})(?:[_x](\d{1,4}))?/i);
if(!m)return 0;
var a=parseInt(m[2],10)||0;
var b=parseInt(m[3]||'0',10)||0;
if(a>0&&b>0)return Math.max(a,b);
if(m[1]&&a>0)return a;
return 0}
function junk(u){
if(!u)return 1;
if(u.indexOf('data:')===0)return 1;
if(!/^https?:/i.test(u))return 1;
var b=String(u).split(/[?#]/)[0];
if(/\.(svg|ico|gif)${'$'}/i.test(b))return 1;
if(/[-_]\d{2,4}x\d{2,4}\.(jpe?g|png|webp)${'$'}/i.test(b))return 1;
var q=qsz(u);
if(q>0&&q<=400)return 1;
if(/(logo|icon|avatar|banner|sprite|favicon|badge|flag|button|emoji|thumb(nail)?s?|placeholder|blank|spacer|transparen|loading|spinner|pixel|profile|rating|share|follow|comment|credits)/i.test(b))return 1;
if(/(?:^|[^a-z0-9])ads?[._\/-]/i.test(b))return 1;
return 0}
var all=[],good=[],idx=0;
var els=document.querySelectorAll('img,source');
for(var i=0;i<els.length;i++){
var el=els[i];
var cs=null;
try{cs=el.currentSrc||el.src||null}catch(e){}
var cands=[cs,el.getAttribute('data-src'),el.getAttribute('data-lazy-src'),el.getAttribute('data-original'),el.getAttribute('data-original-src'),el.getAttribute('data-orig-src'),el.getAttribute('data-lazy'),el.getAttribute('data-url'),el.getAttribute('data-image'),el.getAttribute('data-echo')];
var ss=el.getAttribute('srcset')||el.getAttribute('data-srcset');
if(ss){
var parts=ss.split(','),best='',bw=0;
for(var k=0;k<parts.length;k++){
var tk=parts[k].trim().split(/\s+/);
var u0=tk[0]||'';
var w0=parseInt(String(tk[1]||'').replace(/[^0-9]/g,''),10)||0;
if(u0&&w0>=bw){bw=w0;best=u0}}
if(best)cands.push(best)}
if(el.tagName==='SOURCE'&&el.parentNode){
var pe=el.parentNode.querySelector('img');
if(pe&&pe.src)cands.push(pe.src)}
var pick=null,pj=1;
for(var j=0;j<cands.length;j++){
var u=cands[j];
if(!u)continue;
u=abs(String(u).trim());
if(!u||u.indexOf('data:')===0)continue;
try{if(u===location.href)continue}catch(e){}
if(!pick)pick=u;
if(!junk(u)){pick=u;pj=0;break}
}
if(!pick)continue;
var nw=0,nh=0;
try{nw=el.naturalWidth||0;nh=el.naturalHeight||0}catch(e){}
if(nw&&nh&&Math.max(nw,nh)<300)continue;
all.push([pick,idx]);
if(!pj)good.push([pick,idx]);
idx++
}
function keyOf(u){
var b=String(u).split(/[?#]/)[0];
return b.replace(/[-_]\d{2,4}x\d{2,4}\./i,'.')}
function dedupe(list){
var by={},order=[];
for(var i=0;i<list.length;i++){
var it=list[i],k=keyOf(it[0]);
if(Object.prototype.hasOwnProperty.call(by,k)){
var o=by[k];
if(qsz(it[0])>qsz(o[0]))by[k]=it
}else{by[k]=it;order.push(k)}}
var out=[];
for(var j=0;j<order.length;j++)out.push(by[order[j]][0]);
return out}
var res=dedupe(good);
if(!res.length)res=dedupe(all);
return res;
})()
        """

    }

    private val BG = Color.parseColor("#060607")
    private val CARD = Color.parseColor("#0d0d10")
    private val LINE = Color.parseColor("#1f1f24")
    private val TXT = Color.parseColor("#e8e6e1")
    private val MUT = Color.parseColor("#97948c")
    private val ACC = Color.parseColor("#ff4a3d")

    private lateinit var web: WebView
    private lateinit var urlBox: EditText
    private lateinit var extractBtn: TextView
    private lateinit var countLbl: TextView
    private lateinit var progress: ProgressBar

    private var lastCount = 0

    private val recountHandler = Handler()
    private val recountTick = object : Runnable {
        override fun run() {
            try { recountAsync() } catch (_: Exception) {}
            recountHandler.postDelayed(this, 3000)
        }
    }

    private fun parseLinksRaw(raw: String?): JSONArray? {
        var s = (raw ?: "").trim()
        if (s.isEmpty()) return null
        return try {
            val v = org.json.JSONTokener(s).nextValue()
            when (v) {
                is JSONArray -> v
                is String -> {
                    val inner = org.json.JSONTokener(v).nextValue()
                    if (inner is JSONArray) inner else null
                }
                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BG)
        }

        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(CARD)
            setPadding(12, 10, 12, 10)
        }
        val closeBtn = TextView(this).apply {
            text = "✕"
            setTextColor(TXT)
            textSize = 16f
            setPadding(14, 8, 14, 8)
            setOnClickListener { finish() }
        }
        urlBox = EditText(this).apply {
            setTextColor(TXT)
            setHintTextColor(MUT)
            hint = "آدرس سایت مانهوا…"
            textSize = 13f
            setSingleLine(true)
            imeOptions = EditorInfo.IME_ACTION_GO
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#15151a"))
                cornerRadius = 22f
                setStroke(1, LINE)
            }
            setPadding(20, 16, 20, 16)
            setOnEditorActionListener { _, action, _ ->
                if (action == EditorInfo.IME_ACTION_GO) {
                    goUrl(); true
                } else false
            }
        }
        val goBtn = TextView(this).apply {
            text = "برو"
            setTextColor(Color.WHITE)
            textSize = 13f
            typeface = Typeface.DEFAULT_BOLD
            setPadding(18, 10, 18, 10)
            background = GradientDrawable().apply {
                setColor(ACC)
                cornerRadius = 18f
            }
            setOnClickListener { goUrl() }
        }
        top.addView(closeBtn, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))
        top.addView(urlBox, LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
            marginStart = 6; marginEnd = 6
        })
        top.addView(goBtn, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(top, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))

        progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100
            progress = 0
            progressTintList = android.content.res.ColorStateList.valueOf(ACC)
        }
        root.addView(progress, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(3)))

        web = WebView(this)
        setupWebView()
        root.addView(web, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        val bottom = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(CARD)
            setPadding(12, 10, 12, 10)
        }
        countLbl = TextView(this).apply {
            text = "عکسی پیدا نشده — اول فصل را باز کن"
            setTextColor(MUT)
            textSize = 12f
            setPadding(4, 0, 4, 0)
        }
        extractBtn = TextView(this).apply {
            text = "🖼 استخراج عکس"
            setTextColor(Color.WHITE)
            textSize = 14f
            typeface = Typeface.DEFAULT_BOLD
            setPadding(22, 14, 22, 14)
            background = GradientDrawable().apply {
                setColor(ACC)
                cornerRadius = 24f
            }
            setOnClickListener { extractImages() }
        }
        bottom.addView(countLbl, LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        bottom.addView(extractBtn, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(bottom, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))

        setContentView(root)

        val startUrl = (intent?.getStringExtra(EXTRA_URL) ?: "").trim()
        if (startUrl.startsWith("http")) {
            urlBox.setText(startUrl)
            web.loadUrl(startUrl)
            recountAsync()
        } else {

            val home = if (lastSite.startsWith("http")) lastSite
                else "https://www.google.com"
            web.loadUrl(home)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            builtInZoomControls = true
            displayZoomControls = false
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            userAgentString =
                "Mozilla/5.0 (Linux; Android 10; Pixel 7) " +
                "AppleWebKit/537.36 (KHTML, like Gecko) " +
                "Chrome/120.0.0.0 Mobile Safari/537.36"
        }
        try {
            CookieManager.getInstance().apply {
                setAcceptCookie(true)
                if (Build.VERSION.SDK_INT >= 21) setAcceptThirdPartyCookies(web, true)
            }
        } catch (_: Exception) {}
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?, request: WebResourceRequest?): Boolean {
                return false
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                try {
                    if (url != null && url.startsWith("http")) lastSite = url
                    urlBox.setText(url ?: "")
                } catch (_: Exception) {}
                recountAsync()
            }

            override fun doUpdateVisitedHistory(view: WebView?, url: String?,
                                                isReload: Boolean) {
                super.doUpdateVisitedHistory(view, url, isReload)

                try {
                    if (url != null && url.startsWith("http")) lastSite = url
                    urlBox.setText(url ?: "")
                } catch (_: Exception) {}
                recountAsync()
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progress.progress = newProgress
                progress.visibility =
                    if (newProgress >= 100) View.GONE else View.VISIBLE
            }

            override fun onJsAlert(
                view: WebView?, url: String?, message: String?,
                result: JsResult): Boolean {
                try {
                    Toast.makeText(this@BrowserActivity,
                        message ?: "", Toast.LENGTH_SHORT).show()
                } catch (_: Exception) {}
                result.confirm()
                return true
            }
        }
    }

    private fun smartUrl(input: String?): String? {
        val u = input?.trim() ?: ""
        if (u.isEmpty()) return null
        if (u.startsWith("http://") || u.startsWith("https://")) return u
        var domain = u.indexOf(' ') < 0 && u.indexOf('\t') < 0
        var dots = 0
        var i = 0
        while (domain && i < u.length) {
            val c = u[i]
            if (c == '.') { dots++; i++; continue }
            val ok = (c in 'a'..'z') || (c in 'A'..'Z') || (c in '0'..'9') ||
                    c == '-' || c == '_' || c == ':' || c == '/' ||
                    c == '?' || c == '#' || c == '~'
            if (!ok) domain = false
            i++
        }
        if (domain && dots > 0) return "https://$u"
        return "https://www.google.com/search?q=" +
                java.net.URLEncoder.encode(u, "UTF-8")
    }

    private fun goUrl() {
        val u = smartUrl(urlBox.text.toString()) ?: return
        urlBox.setText(u)
        web.loadUrl(u)
    }

    private fun recountAsync() {
        try {
            web.evaluateJavascript(EXTRACT_JS) { raw ->
                try {
                    val arr = parseLinksRaw(raw)
                    val n = arr?.length() ?: 0
                    runOnUiThread {
                        lastCount = n
                        countLbl.text = if (n > 0) {
                            "$n عکس آماده استخراج"
                        } else {
                            "عکسی پیدا نشده — اول فصل را باز کن"
                        }
                    }
                } catch (_: Exception) {}
            }
        } catch (_: Exception) {}
    }

    private fun extractImages() {
        val cur = try { web.url ?: "" } catch (_: Exception) { "" }
        if (cur.isEmpty() || cur == "about:blank") {
            Toast.makeText(this, "اول یک سایت را باز کن",
                Toast.LENGTH_SHORT).show()
            return
        }
        extractBtn.text = "… در حال استخراج"
        try {
            web.evaluateJavascript(EXTRACT_JS) { raw ->
                runOnUiThread {
                    extractBtn.text = "🖼 استخراج عکس"
                    try {
                        val arr = parseLinksRaw(raw)
                        if (arr == null || arr.length() == 0) {
                            countLbl.text = "عکسی پیدا نشد — تا آخرِ صفحه اسکرول کن"
                            Toast.makeText(this,
                                "هیچ عکسی پیدا نشد — تا آخرِ صفحه اسکرول کن " +
                                "تا عکس‌های تنبل لود بشن",
                                Toast.LENGTH_LONG).show()
                            return@runOnUiThread
                        }
                        val links = StringBuilder()
                        for (i in 0 until arr.length()) {
                            if (i > 0) links.append('\n')
                            links.append(arr.getString(i))
                        }
                        val out = Intent()
                        out.putExtra(EXTRA_LINKS, links.toString())
                        setResult(RESULT_OK, out)
                        Toast.makeText(this,
                            "✅ ${arr.length()} لینک عکس گرفته شد",
                            Toast.LENGTH_SHORT).show()
                        finish()
                    } catch (e: Exception) {
                        Toast.makeText(this,
                            "خطا در استخراج: ${e.message}",
                            Toast.LENGTH_LONG).show()
                    }
                }
            }
        } catch (e: Exception) {
            extractBtn.text = "🖼 استخراج عکس"
            Toast.makeText(this, "خطا: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        try {
            if (web.canGoBack()) web.goBack() else finish()
        } catch (_: Exception) {
            finish()
        }
    }

    override fun onResume() {
        super.onResume()
        recountHandler.removeCallbacks(recountTick)
        recountHandler.postDelayed(recountTick, 1200)
    }

    override fun onPause() {
        recountHandler.removeCallbacks(recountTick)
        super.onPause()
    }

    override fun onDestroy() {
        try { web.destroy() } catch (_: Exception) {}
        super.onDestroy()
    }

    private fun dp(v: Int): Int =
        (v * resources.displayMetrics.density + 0.5f).toInt()
}
