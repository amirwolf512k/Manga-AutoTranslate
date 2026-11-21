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
var W=window;
try{if(/(^|\.)mangaplus\.shueisha\.co\.jp${'$'}/i.test(location.host)&&location.pathname.indexOf('/viewer/')===0)return [location.href];}catch(e){}
if(!W.__MT_FOUND){W.__MT_FOUND={};W.__MT_ORDER=[];}
if(!W.__MT_BLOBS){W.__MT_BLOBS={};}
if(typeof W.__MT_T0!=='number'){W.__MT_T0=0;}
function abs(u){try{var a=document.createElement('a');a.href=u;return a.href}catch(e){return null}}
function qsz(u){
try{
var m=String(u).match(/[?&](?:type|size|w|h|width|height)=(f?)(\d{1,4})(?:[_x](\d{1,4}))?/i);
if(!m)return 0;
var a=parseInt(m[2],10)||0;
var b=parseInt(m[3]||'0',10)||0;
if(a>0&&b>0)return Math.max(a,b);
if(m[1]&&a>0)return a;
return 0
}catch(e){return 0}}
function junk(u){
if(!u)return 1;
u=String(u);
if(u.indexOf('data:')===0)return 1;
if(u.indexOf('blob:')===0)return 1;
if(!/^https?:/i.test(u))return 1;
var b=u.split(/[?#]/)[0];
if(/\.(svg|ico|gif|css|js|mjs|json|html?|xml|txt|pdf|zip|rar|7z|gz|mp4|webm|mp3|m4a|ogg|wav|woff2?|ttf|otf|eot|map)${'$'}/i.test(b))return 1;
if(/[-_]\d{2,4}x\d{2,4}\.(jpe?g|png|webp|avif)${'$'}/i.test(b))return 1;
if(/\/\d{2,4}x\d{2,4}\//i.test(b))return 1;
if(/(login|signin|signup|register|servicelogin|oauth)/i.test(b))return 1;
var q=qsz(u);
if(q>0&&q<=400)return 1;
if(/(logo|icon|avatar|banner|sprite|favicon|badge|flag|button|emoji|thumb(nail)?s?|placeholder|blank|spacer|transparen|loading|spinner|pixel|profile|rating|share|follow|comment|credits)/i.test(b))return 1;
if(/(?:^|[^a-z0-9])ads?[._\/-]/i.test(b))return 1;
if(/\/(covers?|thumbs?|thumbnails?|avatars?|banners?|creatives?|gifs?|decorations?|emojis?|smileys?|stickers?)\//i.test(b))return 1;
if(/(default|anon|guest|blank)[-_]?(pp|avatar|user|profile|image)/i.test(b))return 1;
if(/(pubadx|adservice|adserver|doubleclick|adnxs|propellerads?|onclck|adcash|adsterra|hilltopads?|clickadu|sovrn|taboola|outbrain|zedo|buysellads?|sharethrough|smartadserver|openx|rubicon|criteo|pubmatic|media\.net)/i.test(b))return 1;
return 0}
function keyOf(u){
var b=String(u).split(/[?#]/)[0];
return b.replace(/[-_]\d{2,4}x\d{2,4}\./i,'.')}
function bkey(u){return String(u).split('#')[0]}
function hold(k,b){
try{
if(!b||W.__MT_BLOBS[k])return;
var n=0;for(var p in W.__MT_BLOBS)n++;
if(n<120)W.__MT_BLOBS[k]=b
}catch(e){}}
function capb(u){
try{
if(!u)return;
u=String(u).trim();
if(u.indexOf('blob:')!==0)return;
var k=bkey(u);
if(Object.prototype.hasOwnProperty.call(W.__MT_FOUND,k))return;
W.__MT_FOUND[k]=u;
W.__MT_ORDER.push(u);
try{fetch(u).then(function(r){return r.ok?r.blob():null}).then(function(b){if(b)hold(k,b)}).catch(function(){})}catch(e2){}
}catch(e){}}
function cap(u){
try{
if(!u)return;
u=String(u).trim();
if(u.indexOf('data:')===0)return;
if(u.indexOf('blob:')===0){capb(u);return}
if(!/^https?:/i.test(u))return;
u=abs(u);
if(!u||junk(u))return;
try{if(u===location.href)return}catch(e){}
var k=keyOf(u);
if(Object.prototype.hasOwnProperty.call(W.__MT_FOUND,k))return;
W.__MT_FOUND[k]=u;
W.__MT_ORDER.push(u)
}catch(e){}}
function bestSrcset(ss){
try{
var parts=String(ss).split(','),best='',bw=-1;
for(var k=0;k<parts.length;k++){
var tk=parts[k].trim().split(/\s+/);
var u0=tk[0]||'';
var w0=parseInt(String(tk[1]||'').replace(/[^0-9]/g,''),10)||0;
if(u0&&w0>=bw){bw=w0;best=u0}}
return best
}catch(e){return ''}}
var DATA_ATTS=['data-src','data-lazy-src','data-original','data-original-src','data-orig-src','data-lazy','data-url','data-image','data-echo','data-asurl','data-cfsrc','data-hi-res-src','data-full-src','data-full_image','data-large-src','data-file','data-path','data-actualsrc'];
function nowT(){try{return performance.now()}catch(e){return 0}}
function grabEl(el){
try{
if(!el||el.nodeType!==1)return;
var tg=el.tagName;
if(tg!=='IMG'&&tg!=='SOURCE')return;
el.__MT_SEEN=nowT();
var u='';
try{u=el.currentSrc||el.getAttribute('src')||''}catch(e){}
u=String(u||'');
if(u.indexOf('blob:')===0){capb(u)}
else if(tg==='SOURCE'&&u&&u.indexOf('data:')!==0){cap(u)}
else if(u&&u.indexOf('data:')!==0){
var done=function(){try{var c=el.currentSrc||el.src||'';if(c&&c.indexOf('http')===0)cap(c)}catch(e){}};
try{
if(el.complete&&el.naturalWidth>0){
if(Math.max(el.naturalWidth||0,el.naturalHeight||0)>=300)done();
}else{
el.addEventListener('load',function(){
try{if(Math.max(el.naturalWidth||0,el.naturalHeight||0)>=300)done()}catch(e){}
},{once:true});
}
}catch(e){}
}
try{
var ss=el.getAttribute('srcset')||el.getAttribute('data-srcset');
if(ss){var bs=bestSrcset(ss);if(bs)cap(bs)}
}catch(e){}
for(var j=0;j<DATA_ATTS.length;j++){
try{var v=el.getAttribute(DATA_ATTS[j]);if(v&&v.length>4)cap(v)}catch(e){}
}
}catch(e){}}
function grabTree(n){
try{
if(!n||n.nodeType!==1)return;
if(n.tagName==='IMG'||n.tagName==='SOURCE'){grabEl(n);return}
if(n.querySelectorAll){
var q=n.querySelectorAll('img,source');
for(var i=0;i<q.length;i++)grabEl(q[i])
}
}catch(e){}}
if(!W.__MT_WATCH){
W.__MT_WATCH=1;
try{
var ex=document.querySelectorAll('img,source');
for(var i2=0;i2<ex.length;i2++){try{ex[i2].__MT_SEEN=nowT()}catch(e){}}
}catch(e){}
try{
var obs=new MutationObserver(function(ms){
for(var i3=0;i3<ms.length;i3++){
var m=ms[i3];
try{
if(m.type==='attributes'){grabEl(m.target);continue}
var ns=m.addedNodes;
for(var j2=0;j2<ns.length;j2++)grabTree(ns[j2])
}catch(e){}}
});
obs.observe(document.documentElement||document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['src','srcset']})
}catch(e){}
}
function scanDoc(doc){
try{
var els=doc.querySelectorAll('img');
for(var i=0;i<els.length;i++){
var el=els[i];
try{
var t0=W.__MT_T0||0;
if(el.__MT_SEEN&&el.__MT_SEEN<t0)continue;
el.__MT_SEEN=nowT();
}catch(e){}
var nw=0,nh=0,loaded=false;
try{loaded=!!el.complete&&el.naturalWidth>0;nw=el.naturalWidth||0;nh=el.naturalHeight||0}catch(e){}
var u='';
try{u=el.currentSrc||el.src||''}catch(e){}
if(u&&u.indexOf('data:')===0)u='';
if(u&&u.indexOf('blob:')===0){
if(loaded&&nw&&nh&&Math.max(nw,nh)>=300)capb(u);
u='';
}
if(u&&loaded&&nw&&nh&&Math.max(nw,nh)<300)u='';
if(u)cap(u);
try{
var ss=el.getAttribute('srcset')||el.getAttribute('data-srcset');
if(ss){var bs=bestSrcset(ss);if(bs)cap(bs)}
}catch(e){}
for(var j=0;j<DATA_ATTS.length;j++){
try{
var v=el.getAttribute(DATA_ATTS[j]);
if(v&&v.length>4)cap(v)
}catch(e){}}
}
}catch(e){}
try{
var sos=doc.querySelectorAll('source');
for(var i4=0;i4<sos.length;i4++){
var so=sos[i4];
try{
var t02=W.__MT_T0||0;
if(so.__MT_SEEN&&so.__MT_SEEN<t02)continue;
so.__MT_SEEN=nowT();
var s2=so.getAttribute('srcset')||so.getAttribute('data-srcset')||so.getAttribute('src');
if(s2){var b2=bestSrcset(s2);if(!b2)b2=s2;if(b2)cap(b2)}
}catch(e){}}
}catch(e){}
try{
var as=doc.querySelectorAll('a[href]');
for(var i5=0;i5<as.length;i5++){
var h=as[i5].getAttribute('href')||'';
if(/^https?:/i.test(h)&&/\.(jpe?g|png|webp|avif|bmp)([?#]|${'$'})/i.test(h))cap(h)}
}catch(e){}
try{
var st=doc.querySelectorAll('[style*="url("]');
for(var i6=0;i6<st.length;i6++){
var mm=String(st[i6].getAttribute('style')||'').match(/url\((['"]?)([^'")]+)\1\)/i);
if(mm&&mm[2])cap(mm[2])}
}catch(e){}}
function scanAll(){
try{scanDoc(document)}catch(e){}
try{
var fs=document.querySelectorAll('iframe');
for(var i=0;i<fs.length;i++){
try{var d=fs[i].contentDocument;if(d)scanDoc(d)}catch(e){}}
}catch(e){}
try{
var of=window.frames;
for(var j=0;j<of.length;j++){
try{var d2=of[j].document;if(d2)scanDoc(d2)}catch(e){}}
}catch(e){}}
function perfPass(){
try{
var rs=performance.getEntriesByType('resource');
var tp=W.__MT_T0||0;
for(var i=0;i<rs.length;i++){
var en=rs[i]||{};
var n=String(en.name||'');
if(!n)continue;
try{if(en.startTime<tp)continue}catch(e){}
var b=n.split(/[?#]/)[0];
var t=String(en.initiatorType||'');
if(/\.(jpe?g|png|webp|avif|bmp|tiff?)${'$'}/i.test(b)){cap(n);continue}
if(t==='img'){if(n.indexOf('blob:')===0){capb(n)}else{cap(n)}}
}
}catch(e){}}
function scriptPass(){
try{
if(W.__MT_ORDER.length)return;
var sc=document.querySelectorAll('script');
var re=/https?:\\?\/\\?\/[^"'\s\\<>()[\]]+?\.(?:jpe?g|png|webp|avif|bmp)(?:\?[^"'\\\s<>()[\]]*)?/gi;
var m,guard=0;
for(var i=0;i<sc.length&&guard<800;i++){
var txt='';
try{txt=sc[i].textContent||''}catch(e){continue}
if(!txt||txt.length<10)continue;
re.lastIndex=0;
while((m=re.exec(txt))&&guard<800){
guard++;
try{cap(m[0].replace(/\\\//g,'/'))}catch(e){}}}
}catch(e){}}
scanAll();
perfPass();
scriptPass();
try{return W.__MT_ORDER.slice(0,400)}catch(e){return []}
})()
        """

        private const val SCROLL_JS = """
(function(){
try{
if(window.__MT_SCROLLING)return;
window.__MT_SCROLLING=1;
window.__MT_SCROLL_DONE=0;
var step=Math.max(500,Math.floor(window.innerHeight*0.85));
var y=0,n=0,stable=0,lastH=0;
function H(){try{return Math.max(document.body?document.body.scrollHeight:0,document.documentElement?document.documentElement.scrollHeight:0)}catch(e){return 0}}
lastH=H();
function tick(){
try{
y+=step;
window.scrollTo(0,y);
n++;
var h=H();
if(h===lastH)stable++;else{stable=0;lastH=h}
var atBottom=(y+window.innerHeight>=h-8);
if((atBottom&&stable>=3)||n>200){
try{window.scrollTo(0,0)}catch(e){}
window.__MT_SCROLL_DONE=1;
return
}
setTimeout(tick,280)
}catch(e){window.__MT_SCROLL_DONE=1}
}
tick()
}catch(e){try{window.__MT_SCROLL_DONE=1}catch(e2){}}
})()
        """

        private const val CLEAR_STORE_JS = """
(function(){try{window.__MT_FOUND={};window.__MT_ORDER=[];window.__MT_BLOBS={};try{window.__MT_T0=(window.performance&&performance.now)?performance.now():0}catch(e){window.__MT_T0=0}}catch(e){}})()
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
    private lateinit var dlBtn: TextView
    private lateinit var countLbl: TextView
    private lateinit var progress: ProgressBar

    private val foundStore = java.util.LinkedHashSet<String>()
    private var chapterKeyNow = ""
    private var dlDir: java.io.File? = null
    private var dlDone = 0
    private var dlOk = 0

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
            text = "🖼 استخراج لینک"
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
        dlBtn = TextView(this).apply {
            text = "⬇ استخراج دانلود"
            setTextColor(Color.WHITE)
            textSize = 14f
            typeface = Typeface.DEFAULT_BOLD
            setPadding(22, 14, 22, 14)
            background = GradientDrawable().apply {
                setColor(Color.parseColor("#2d3649"))
                setStroke(1, ACC)
                cornerRadius = 24f
            }
            setOnClickListener { downloadImages() }
        }
        bottom.addView(countLbl, LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        bottom.addView(extractBtn, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT))
        val dlLp = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT)
        dlLp.setMargins(8, 0, 0, 0)
        bottom.addView(dlBtn, dlLp)
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
        try {
            web.addJavascriptInterface(object {
                @android.webkit.JavascriptInterface
                fun recv(idx: Int, total: Int, dataUrl: String?, srcUrl: String?) {
                    onDlItem(idx, total, dataUrl ?: "", srcUrl ?: "")
                }

                @android.webkit.JavascriptInterface
                fun done(total: Int) {
                    onDlDone(total)
                }
            }, "MtDl")
        } catch (_: Exception) {}
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

    private fun chapterKey(raw: String?): String {
        val u = (raw ?: "").trim()
        if (!u.startsWith("http")) return u
        return try {
            val p = java.net.URI(u)
            val host = p.host ?: ""
            var path = p.path ?: ""
            while (path.endsWith("/")) path = path.substring(0, path.length - 1)
            val list = if (path.isEmpty()) mutableListOf()
                else path.substring(1).split("/").filter { it.isNotEmpty() }.toMutableList()
            var strips = 0
            while (list.size >= 2 && strips < 2) {
                val last = list.last()
                if (!Regex("^\\d{1,4}$").matches(last)) break
                val parent = list[list.size - 2]
                val parentNumeric = Regex("^\\d+$").matches(parent)
                val parentChapMark = Regex("(ch|chap|chapter|episode|ep|sec|part)[-_]?\\d",
                    RegexOption.IGNORE_CASE).containsMatchIn(parent)
                if (parentNumeric || parentChapMark) { list.removeAt(list.size - 1); strips++ }
                else break
            }
            val q = p.rawQuery ?: ""
            val kept = q.split("&").filter { it.isNotBlank() }
                .filter { !Regex("^(page|pg|pagina)$", RegexOption.IGNORE_CASE)
                    .matches(it.substringBefore('=')) }
                .sorted()
            host + (if (list.isEmpty()) "" else "/" + list.joinToString("/")) +
                (if (kept.isEmpty()) "" else "?" + kept.joinToString("&"))
        } catch (_: Exception) {
            u.substringBefore('#').substringBefore('?')
        }
    }

    private fun syncChapterKey() {
        try {
            val cur = try { web.url } catch (_: Exception) { null }
            val k = chapterKey(cur)
            if (k != chapterKeyNow) {
                chapterKeyNow = k
                foundStore.clear()
                try { web.evaluateJavascript(CLEAR_STORE_JS, null) } catch (_: Exception) {}
            }
        } catch (_: Exception) {}
    }

    private fun mergeFound(arr: JSONArray?): Int {
        if (arr != null) {
            for (i in 0 until arr.length()) {
                val u = arr.optString(i)
                if (u.isNotBlank()) foundStore.add(u)
            }
        }
        return foundStore.size
    }

    private fun storeSnapshot(): JSONArray {
        val arr = JSONArray()
        for (u in foundStore) arr.put(u)
        return arr
    }

    private fun isMangaPlusViewerUrl(u: String): Boolean {
        return try {
            val p = java.net.URI(u)
            val h = (p.host ?: "").lowercase()
            (h == "mangaplus.shueisha.co.jp" ||
                    h == "www.mangaplus.shueisha.co.jp") &&
                (p.path ?: "").startsWith("/viewer/")
        } catch (_: Exception) { false }
    }

    private fun recountAsync() {
        try {
            syncChapterKey()
            web.evaluateJavascript(EXTRACT_JS) { raw ->
                try {
                    val arr = parseLinksRaw(raw)
                    runOnUiThread {
                        val n = mergeFound(arr)
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

    private fun startAutoScroll(done: () -> Unit) {
        try {
            web.evaluateJavascript(SCROLL_JS, null)
        } catch (_: Exception) {}
        val h = Handler()
        val t0 = System.currentTimeMillis()
        val tick = object : Runnable {
            override fun run() {
                try {
                    web.evaluateJavascript(
                        "(window.__MT_SCROLL_DONE===1)?1:0") { v ->
                        val finished = "1" == v ||
                                System.currentTimeMillis() - t0 > 60000
                        if (finished) {
                            h.postDelayed({ done() }, 700)
                        } else {
                            h.postDelayed(this, 800)
                        }
                    }
                } catch (_: Exception) {
                    done()
                }
            }
        }
        h.postDelayed(tick, 900)
    }

    private fun hasBlobs(arr: JSONArray?): Boolean {
        if (arr == null) return false
        try {
            for (i in 0 until arr.length()) {
                if (arr.optString(i).startsWith("blob:")) return true
            }
        } catch (_: Exception) {}
        return false
    }

    private fun extractWithScroll(then: (JSONArray?) -> Unit) {
        try {
            syncChapterKey()
            web.evaluateJavascript(EXTRACT_JS) { raw ->
                runOnUiThread {
                    val arr = parseLinksRaw(raw)
                    mergeFound(arr)
                    val snapshot = storeSnapshot()
                    if (snapshot.length() > 0 && !hasBlobs(snapshot)) {
                        then(snapshot)
                        return@runOnUiThread
                    }
                    countLbl.text = "… در حال آماده‌سازی صفحه (اسکرول خودکار)"
                    startAutoScroll {
                        try {
                            syncChapterKey()
                            web.evaluateJavascript(EXTRACT_JS) { raw2 ->
                                runOnUiThread {
                                    val arr2 = parseLinksRaw(raw2)
                                    mergeFound(arr2)
                                    then(storeSnapshot())
                                }
                            }
                        } catch (_: Exception) {
                            then(storeSnapshot())
                        }
                    }
                }
            }
        } catch (_: Exception) {
            then(null)
        }
    }

    private fun httpFetch(u: String): ByteArray? {
        return try {
            val c = java.net.URL(u).openConnection() as java.net.HttpURLConnection
            c.connectTimeout = 15000
            c.readTimeout = 40000
            c.setRequestProperty("User-Agent",
                "Mozilla/5.0 (Linux; Android 10; Pixel 7) " +
                "AppleWebKit/537.36 (KHTML, like Gecko) " +
                "Chrome/120.0.0.0 Mobile Safari/537.36")
            try {
                val ck = CookieManager.getInstance().getCookie(u)
                if (!ck.isNullOrEmpty()) c.setRequestProperty("Cookie", ck)
            } catch (_: Exception) {}
            try {
                val ref = web.url
                if (ref != null && ref.startsWith("http"))
                    c.setRequestProperty("Referer", ref)
            } catch (_: Exception) {}
            val code = c.responseCode
            if (code < 200 || code >= 300) {
                c.disconnect()
                return null
            }
            val bo = java.io.ByteArrayOutputStream()
            c.inputStream.use { ins ->
                val buf = ByteArray(16384)
                while (true) {
                    val n = ins.read(buf)
                    if (n <= 0) break
                    bo.write(buf, 0, n)
                }
            }
            c.disconnect()
            if (bo.size() == 0) null else bo.toByteArray()
        } catch (_: Exception) {
            null
        }
    }

    private fun extOf(head: String, data: ByteArray): String {
        val m = Regex("data:image/(jpe?g|png|webp|bmp)").find(head.lowercase())
        if (m != null) {
            val g = m.groupValues[1]
            return if (g == "jpeg") ".jpg" else "." + g
        }
        if (data.size >= 3 && (data[0].toInt() and 0xFF) == 0xFF
                && (data[1].toInt() and 0xFF) == 0xD8) return ".jpg"
        if (data.size >= 4 && (data[0].toInt() and 0xFF) == 0x89
                && data[1] == 0x50.toByte()) return ".png"
        if (data.size >= 12 && data[0] == 'R'.code.toByte()
                && data[1] == 'I'.code.toByte()
                && data[8] == 'W'.code.toByte()) return ".webp"
        return ".jpg"
    }

    private fun onDlItem(idx: Int, total: Int, dataUrlIn: String, srcUrl: String) {
        try {
            val dir = dlDir ?: return
            var dataUrl = dataUrlIn.trim()
            if (dataUrl.isEmpty() || !dataUrl.startsWith("data:image/")) {
                val bytes = httpFetch(srcUrl)
                if (bytes != null) {
                    dataUrl = "data:image/jpeg;base64," +
                            android.util.Base64.encodeToString(bytes,
                                android.util.Base64.NO_WRAP)
                }
            }
            if (dataUrl.startsWith("data:image/")) {
                val head = dataUrl.substringBefore(",", "")
                val b64 = dataUrl.substringAfter(",", "")
                val bytes = try {
                    android.util.Base64.decode(b64, android.util.Base64.DEFAULT)
                } catch (_: Exception) {
                    null
                }
                if (bytes != null && bytes.isNotEmpty()) {
                    val f = java.io.File(dir, "page_%03d%s".format(idx + 1,
                            extOf(head, bytes)))
                    java.io.FileOutputStream(f).use { it.write(bytes) }
                    dlOk++
                }
            }
            dlDone++
            val done = dlDone
            val ok = dlOk
            runOnUiThread {
                countLbl.text = "⬇ $done/$total" + (if (ok > 0) " — $ok ✓" else "")
            }
        } catch (_: Exception) {}
    }

    private fun onDlDone(total: Int) {
        runOnUiThread {
            try {
                val dir = dlDir
                val files = dir?.listFiles()?.sortedBy { it.name } ?: emptyList()
                if (files.isNotEmpty()) {
                    val out = android.content.Intent()
                    out.putExtra(EXTRA_LINKS, files.joinToString("\n") { it.absolutePath })
                    setResult(RESULT_OK, out)
                    Toast.makeText(this, "✅ ${files.size} عکس دانلود شد",
                        Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this, "هیچ عکسی دانلود نشد",
                        Toast.LENGTH_LONG).show()
                }
                finish()
            } catch (_: Exception) {}
        }
    }

    private fun startDownloadAll(urls: List<String>) {
        try {
            val base = getExternalFilesDir(null) ?: filesDir
            dlDir = java.io.File(base, "manga_dl_" + System.currentTimeMillis())
            dlDir?.mkdirs()
            dlDone = 0
            dlOk = 0
        } catch (e: Exception) {
            Toast.makeText(this, "خطا در آماده‌سازی دانلود: ${e.message}",
                Toast.LENGTH_LONG).show()
            return
        }
        val arr = JSONArray(urls)
        val js = buildString {
            append("(function(){try{var urls=").append(arr.toString()).append(";")
            append("function toData(u){")
            append("try{var k=String(u).split('#')[0];")
            append("if(window.__MT_BLOBS&&window.__MT_BLOBS[k]){")
            append("var bb=window.__MT_BLOBS[k];")
            append("return new Promise(function(res){")
            append("try{var f=new FileReader();")
            append("f.onload=function(){res(String(f.result||''))};")
            append("f.onerror=function(){res('')};")
            append("f.readAsDataURL(bb)}")
            append("catch(e){res('')}})}}catch(e){}")
            append("return fetch(u,{credentials:'include'})")
            append(".then(function(r){if(!r.ok)return '';return r.blob()})")
            append(".then(function(b){if(!b)return '';return new Promise(function(res){")
            append("try{var f=new FileReader();")
            append("f.onload=function(){res(String(f.result||''))};")
            append("f.onerror=function(){res('')};f.readAsDataURL(b)}")
            append("catch(e){res('')}})})}")
            append("var i=0;function step(){")
            append("if(i>=urls.length){try{window.MtDl.done(urls.length)}catch(e){}return}")
            append("var idx=i;var u=urls[i];i++;")
            append("toData(u).then(function(d){")
            append("try{window.MtDl.recv(idx,urls.length,d||'',u)}catch(e){}step()})")
            append(".catch(function(){")
            append("try{window.MtDl.recv(idx,urls.length,'',u)}catch(e){}step()})}")
            append("step()}catch(e){try{window.MtDl.done(0)}catch(e2){}}})()")
        }
        try {
            web.evaluateJavascript(js, null)
        } catch (e: Exception) {
            Toast.makeText(this, "خطا در شروع دانلود: ${e.message}",
                Toast.LENGTH_LONG).show()
        }
    }

    private fun downloadImages() {
        val cur = try { web.url ?: "" } catch (_: Exception) { "" }
        if (cur.isEmpty() || cur == "about:blank") {
            Toast.makeText(this, "اول یک سایت را باز کن",
                Toast.LENGTH_SHORT).show()
            return
        }
        dlBtn.text = "… در حال دانلود"
        extractWithScroll { arr ->
            dlBtn.text = "⬇ استخراج دانلود"
            try {
                if (arr == null || arr.length() == 0) {
                    countLbl.text = "عکسی پیدا نشد — صفحه فصل را باز کن"
                    Toast.makeText(this@BrowserActivity,
                        "هیچ عکسی پیدا نشد — صفحه فصل را باز کن",
                        Toast.LENGTH_LONG).show()
                    return@extractWithScroll
                }
                val n = arr.length()
                if (n == 1 && isMangaPlusViewerUrl(arr.getString(0))) {
                    val out = Intent()
                    out.putExtra(EXTRA_LINKS, arr.getString(0))
                    setResult(RESULT_OK, out)
                    Toast.makeText(this@BrowserActivity,
                        "لینک فصل مانگاپلاس گرفته شد — " +
                        "موتور خودش عکس‌ها را از API رسمی می‌گیرد",
                        Toast.LENGTH_LONG).show()
                    finish()
                    return@extractWithScroll
                }
                val urls = ArrayList<String>(n)
                for (i in 0 until n) urls.add(arr.getString(i))
                countLbl.text = "⬇ 0/$n"
                startDownloadAll(urls)
            } catch (e: Exception) {
                Toast.makeText(this@BrowserActivity,
                    "خطا در دانلود: ${e.message}",
                    Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun extractImages() {
        val cur = try { web.url ?: "" } catch (_: Exception) { "" }
        if (cur.isEmpty() || cur == "about:blank") {
            Toast.makeText(this, "اول یک سایت را باز کن",
                Toast.LENGTH_SHORT).show()
            return
        }
        extractBtn.text = "… در حال استخراج"
        extractWithScroll { arr ->
            extractBtn.text = "🖼 استخراج عکس"
            try {
                if (arr == null || arr.length() == 0) {
                    countLbl.text = "عکسی پیدا نشد — صفحه فصل را باز کن"
                    Toast.makeText(this,
                        "هیچ عکسی پیدا نشد — صفحه فصل را باز کن",
                        Toast.LENGTH_LONG).show()
                    return@extractWithScroll
                }
                if (hasBlobs(arr)) {
                    countLbl.text = "${arr.length()} عکس آماده — دکمه «استخراج دانلود» را بزن"
                    Toast.makeText(this,
                        "این سایت عکس‌ها را داخل مرورگر رمزگشایی می‌کند " +
                        "(${arr.length()} صفحه آماده) — " +
                        "از دکمه «استخراج دانلود» استفاده کن",
                        Toast.LENGTH_LONG).show()
                    return@extractWithScroll
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
