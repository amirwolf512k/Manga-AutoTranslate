#!/usr/bin/env python3
"""Text filter — tiny char-ngram softmax classifier (pure numpy).

Trains on a data-driven corpus (dialogue / sfx / ads / junk) and exports
models/text_filter.npz. Runtime inference needs ONLY numpy — no fasttext,
no onnxruntime — so it runs on PC, Web and Android (Chaquopy) alike.

The classification «rules» live in the TRAINING DATA, not in engine code:
the model learns SFX/ads/junk patterns from labeled examples.

Corpus sources (v2 — massively expanded after user feedback):
  * dialogue: Tatoeba real sentences (en/ja/ko/zh, tools/.data/tatoeba_*.txt,
    CC-BY) + manga-domain seeds + shout/short variants
  * sfx: ~260 EN onomatopoeia bases + JA/KO/ZH lists, with realistic
    mutations (caps, stretch, repetition, hyphenation, punct)
  * ads/promo: scanlation credits, reader-site templates, domains/URLs,
    socials, chapter headers, reader-UI strings — templated with real
    site/team/handle vocabularies
  * junk: digit/symbol noise, random alpha mash, OCR artifacts

Usage:
  python3 tools/text_filter.py train            # build corpus + train + eval
  python3 tools/text_filter.py eval "BOOOM!!!"  # quick test
  python3 tools/text_filter.py probe            # run the realistic probe set
"""
import os, sys, re, math, json, random, unicodedata
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "models", "text_filter.npz")
B = 1 << 18          # hash buckets
DIM_CLASSES = ["dialogue", "sfx", "ads", "junk"]
SEED = 137
DATA_DIR = os.path.join(ROOT, "tools", ".data")

# ---------------------------------------------------------------- featurize
def _fnv1a(s: str) -> int:
    h = 2166136261
    for ch in s.encode("utf-8", "ignore"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h

def _normalize(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "")
    t = t.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t

def featurize(text: str, buckets: int = B, dense: bool = False):
    """hashed char-ngrams (1..4, word-bounded) + word uni/bigrams → sparse
    (indices, values) or dense L2-normalized vector when dense=True"""
    t = _normalize(text)
    words = t.split(" ")
    feats = []
    for w in words:
        if not w:
            continue
        ww = "<" + w + ">"
        feats.append("w:" + w)
        for n in range(1, 5):
            for i in range(0, max(1, len(ww) - n + 1)):
                feats.append("c%d:%s" % (n, ww[i:i + n]))
    for i in range(len(words) - 1):
        feats.append("b:" + words[i] + "_" + words[i + 1])
    if not feats:
        feats = ["c1:<empty>"]
    counts = {}
    for f in feats:
        k = _fnv1a(f) % buckets
        counts[k] = counts.get(k, 0.0) + 1.0
    idx = np.fromiter(counts.keys(), dtype=np.int64, count=len(counts))
    val = np.fromiter(counts.values(), dtype=np.float32,
                      count=len(counts))
    np.sqrt(val, out=val)
    n = float(np.linalg.norm(val))
    if n > 0:
        val /= n
    if dense:
        v = np.zeros(buckets, dtype=np.float32)
        v[idx] = val
        return v
    return idx, val

# ---------------------------------------------------------------- vocab
SITES = [
    "MangaDex", "MangaPlus", "VIZ", "Webtoon", "Naver", "Kakao", "KakaoPage",
    "Lezhin", "Tappytoon", "Tapas", "Bilibili", "Kuaikan", "Webcomics",
    "ToonHub", "ToonVerse", "ScanZone", "ZeroScans", "AsuraScans",
    "FlameComics", "FlameScans", "LuminousScans", "NightScans", "DrakeScans",
    "RawKuna", "ManhuaPlus", "ManhuaPlus", "ComicK", "Bato", "BatoTo",
    "Mangakakalot", "Manganato", "Mangabuddy", "Mangadex", "WebtoonHub",
    "Toonily", "ManhwaClan", "ManhwaHentai", "SuryaScans", "ArenaScans",
    "CyanScans", "AnigliScans", "SigmaScans", "VoidScans", "TritonScans",
    "HachiScans", "IlluminatiScans", "MangaSushi", "MangaClash", "Mangaowl",
    "MangaFire", "Manga4Life", "MangaSee", "ReadComicBooks", "Comikey",
    "Azuki", "Inkr", "Pocket Comics", "Secret Nobles", "Lilydusk",
]
TEAMS = [
    "Zero Scans", "Asura Scans", "Flame Comics", "Luminous Scans",
    "Night Scans", "Void Scans", "Surya Scans", "Drake Scans",
    "Triton Scans", "Hachi Scans", "Cyan Scans", "Sigma Scans",
    "Arena Scans", "Anigli Scans", "Illuminati Scans", "Manga Squad",
    "MangaInvasion", "Shiro Scans", "Kataki Scans", "Kuma Scans",
    "Moe Scans", "HunGRR Scans", "Beru Scans", "Igor Scans",
    "Omega Scans", "Shadow Scans", "Grand Line Scans", "One Piece Scans",
    "Nocturne Scans", "Aurora Scans", "Silent Sky Scans", "Red Hawk Scans",
    "Proxy Scans", "Perverse Alchemy", "Hachirumi Scans", "落雪汉化组",
    "猫咪汉化组", "하나스캔", "블루스캔",
]
HANDLES = [
    "zeroscans", "asurateam", "flamecomics", "void_scans", "suryascans",
    "drakescans", "hachiscans", "nocturnescans", "aurorascans", "moe_scans",
    "shiroTeam", "kumascans", "omegaScans", "redhawkgg", "proxyteam",
    "luminousscans", "sigmaScans", "nightscans", "triton_team", "igorscans",
]
BRANDS = [
    "Crunchyroll", "Honey", "NordVPN", "Raid Shadow Legends", "Skillshare",
    "Audible", "HelloFresh", "Raycon", "Manscaped", "Displate",
]
TLDS = ["com", "org", "net", "io", "xyz", "tv", "gg", "me", "to", "cc"]

ROLES_EN = [
    ("scanlated by", "scanlation group"), ("scans by", "scan team"),
    ("translated by", "translation team"), ("tl by", "tl team"),
    ("typeset by", "ts team"), ("proofread by", "pr team"),
    ("cleaned by", "clean team"), ("redraw by", "rd team"),
    ("cl by", "quality check"), ("edit by", "qc team"),
]

ADS_BASE = [
    "read free on", "read more at", "continue reading at", "full chapter at",
    "visit our website", "follow us on", "join our discord",
    "support us on patreon", "official release at", "scan by",
    "translated by", "typeset by", "proofread by", "cleaned by",
    "download more at", "for more manga visit", "your ad here",
    "sponsored by", "advertisement", "all rights reserved",
    "please support the official release", "available now on",
    "new chapter every", "update every", "latest chapter",
    "exclusive on", "only on", "presented by", "brought to you by",
    "in cooperation with", "special thanks to",
    "like and subscribe", "don't forget to", "check out",
    "manga updates", "novel updates", "webtoon original", "original story",
    "based on the novel", "serialized in", "published by", "licensed by",
    "read now", "start reading", "read first", "free to read",
    "daily pass", "unlock episode", "unlock chapter", "buy coins",
    "download the app", "get the app", "install now", "sign up",
    "log in", "tap to read", "scroll down", "swipe up", "swipe left",
    "best viewed on mobile", "click here", "click now", "apply now",
    "limited offer", "limited time", "sale now on", "buy now",
    "order now", "shop now", "learn more", "see more", "show more",
    "load more", "watch now", "play now", "subscribe now",
    "not sold in stores", "recommended for you", "you may also like",
    "recommended series", "similar series", "trending now",
    "hot series", "new release", "coming soon", "stay tuned",
    "follow for more", "turn on notifications", "share with friends",
    "rate this series", "leave a comment", "report issue",
    "support the artist", "buy the volume", "buy the tankobon",
    "official english release", "read legally", "support the author",
    # credit-page roles (must stay promo, never erased)
    "quality check", "typesetter", "proofreader", "translator", "cleaner",
    "redrawer", "author", "artist", "story", "art by", "manga by",
    "original work", "original story by", "lettering", "graphics",
]

CHAPTER_HEADERS = [
    "CHAPTER {n}", "Chapter {n}", "Ch. {n}", "CH {n}", "chapter {n}",
    "Episode {n}", "EP {n}", "Ep. {n}", "ep {n}", "episode {n}",
    "第{n}話", "第{n}话", "{n}화", "제{n}화", "第{n}章", "Act {n}",
    "Part {n}", "Round {n}", "Stage {n}", "Level {n}", "Case {n}",
    "File {n}", "Log {n}", "Entry {n}", "Vol. {n}", "Vol {n}", "Volume {n}",
    "Track {n}", "Mission {n}", "Quest {n}", "Chapter {n}:",
    "Side Story {n}", "Extra Chapter {n}", "Interlude {n}",
]

# ad imperatives — heavy weight (OCR hits them often and model is weak here)
AD_CTA = [
    "CLICK HERE", "READ NOW", "SHOP NOW", "LEARN MORE", "WATCH NOW",
    "SIGN UP", "SUBSCRIBE", "DOWNLOAD NOW", "PLAY FREE", "GET STARTED",
    "TRY NOW", "JOIN NOW", "SEE MORE", "APPLY NOW", "BUY NOW",
    "read here", "watch free", "no ads", "ad-free", "premium",
    "unlock all", "VIP", "free coins", "daily bonus", "event now",
]

END_MARKS = [
    "To be continued", "TO BE CONTINUED", "To Be Continued...", "Continued...",
    "to be continued in the next chapter", "Next chapter", "Next episode",
    "Previous chapter", "Previous episode", "See you next chapter",
    "See you next week", "See you in the next issue", "つづく", "つづく…",
    "次回へ続く", "次号に続く", "다음 화에 계속", "계속", "다음 편에 계속",
    "未完待续", "下集待續", "待续", "END", "Fin.", "FIN", "The End", "完",
    "おわり", "おしまい", "완결", "完結", "完结", "Author's note",
    "Afterword", "Director's note", "Special thanks", "Credits",
    "Credit page", "Staff", "Cast",
]

# ---------------------------------------------------------------- SFX lists
SFX_EN = """boom bam pow zap wham crash bang clang thud slam smash crack
crunch snap pop fizz buzz hum ring chime ding dong beep boop honk vroom
zoom whoosh swoosh swish whip slash slice stab pierce shing clank clink
thump thwack biff sock punch kick jab rumble roar growl hiss
bark howl whimper yelp shriek screech squeak creak groan moan sigh
gasp pant wheeze cough sniff sob blub drip splash sploosh slosh gurgle
gulp slurp chomp munch nibble chew burp hiccup yawn sniffle
flutter flap rustle crackle sizzle fizzle
kaboom kapow boosh fwoosh shwoosh krakk krrsh shaaah hwaaah
thud dooom doom vwoom vroom kwaan kwan klang kling shlink shing
tak tk tok tik klik clack click chik chk tsk tsk-tsk
katsu pata pat tap plop plink plonk plunk kerplunk kersplash
splish splosh splat splort squish squelch sproing boing twang
thwip thwapp whump whomp woomph fwip fwap fwump thwap womp
bonk bop konk chunk klunk thunk chink clonk clop clippity
scrape screech scratch scratchy skid skrrt skrrreee nnn vree
hiss ssss pssh psst shhh shh shush wheee yipe yip arf woof
meow purr mew chirp tweet caw coo hoot quack oink moo baa
gobble cluck crow cockadoodledoo buzzz bzzz bzzt zzt zzz
grr growlf grrr ruff growl snap-hiss clatter rattle jangle
jingle tinkle chime-ding clink-clink rat-tat-tat ratatat
rat-a-tat-tat bang-bang pop-pop pew-pew pew pyoo beam zap-zap
ka-boom ka-chunk ka-ching cha-ching ker-chunk kachunk
bada-boom bada-bing baroom ba-doom dum-dum dun-dun-duuun ta-da
tada fanfare flourish roll-roll tadaaa
drip-drop dripdrop pitter-patter patter pata-pata
hummm whirr whir whizz whiz zzzzip zip zzzip zzzap
swoosh woosh whoosh whush fwush shwoop shlup slosh spurt squirt
glug glub blub-blub gurgle gargle blorp burble bloop blip
kriiish shraaa krrrsh grrrrsh hwoooosh fwaaah shaaaah
kwoom kwom woomm woomphe Doom doom-doom doomm
kwaan kwaann kwaaan gooon goooon byuuun byuuuun
biiii bonn booon paan paann baan baann
gogogo dododo bababa gagaga dadada zuzuzuzu
zag zig zog zug crick crack crick-crack snap-crackle
kafooey kerfuffle blammo blam kablooey kersplode kersploosh
swish-clang clang-clang boom-boom boomchaka
huff puff phew wheeze-huff snort snrk hmph hmpf
yawn yaaawn sleepy snore zzz-mimi
heave ho hoist yank tug rip tear shrrrip riiiip
zzzip-snap pop-snap snap-pop crack-snap boom-slam
swipe swoop dive glide zoom-zoom vroom-vroom skreeee
chomp-chomp nom nom-nom munch-munch crunch-crunch gobble
gulp-gulp slurrrp slurp-slurp sssllluuurrrp
sniff-sniff sniffle snff hnnngh hngh nngh
flick flip flop flim-flam swish-swish whip-whip
pewm pewm-pewm pyuun byun byunn shun shuuun
tok-tok-tok tokkon kop-kop knock-knock knock
ting ting-a-ling ding-dong bell-ring
siren weeoo wee-oo wail woooo
mumble murmur mutter whisper hush-hush psst-psst
boom-slam crash-bang smash-boom wallup wallopped
ka-rack krr-ack grrrack krakka krakaan
shink shnkt shhhink sringg schwing schiing
fwip-fwip fwap-fwap flutter-flutter pata-flap
""" .split()

SFX_JA = """ドン バン ゴゴゴ ザアア ドダダ ガタガタ ガシャン バキッ ボカッ
ゴキッ メキッ ズシッ ドカン バアアン キラキラ ピカッ カチッ パチッ
サッ シュッ ヒュウ ビュウ ザッ ワアワア ウワアア ギャアア ウォアア
ドクドク バクバク ズキズキ キリキリ ジリジリ ムカムカ イライラ
ペコペコ キョロキョロ ジロジロ ニヤニヤ ウフフ アハハ オホホ
エヘヘ ウシシ ケケケ ガハハ ニャア ワン モー メー コケコッ
チュンチュン カアカア ケロケロ ブンブン ザンザン カラン コロン
ドォン ゴォン バォン ドオオオ ゴオオオ バオオオ ズオオオ
ゴボッ ボゴッ ズルズル ズズズ ゴクリ ペロッ パクッ ガブッ カプリ
ボキッ グシャ ガシャ ガラガラ ゴロゴロ ドスッ ドサッ バタッ ドタッ
バタバタ ドタバタ カツ カツカツ タッ タタッ ダダッ ダダダダ タタタタ
ドドドド ザワザワ ガヤガヤ ワイワイ ザーッ ザッザッ シャーッ
キラ ピカ チラ ニヤ ニタ ニコッ ウッ ウフッ ヒャッ ハァ フゥー
ゼイゼイ ゼーゼー ハーハー スースー ゴクッ コクッ チュッ チュルル
ペチャクチャ モゴモゴ ブツブツ ツツツ チチチ ジジッ ビビビ バチバチ
ピキピキ メキメキ ズキッ ズキューング チクチク ズンズン ドキッ
ゾクッ ゾワゾワ ヒヤッ ヒヤヒヤ サラサラ ザラザラ ヌルヌル
グニャ グニグニ ベチッ ビシッ ビシバシ ペチペチ バシッ バシバシ
ガンッ ゴンッ コンコン ノック ピンポン チャリン ジリリ ウィーン
ブーッ パーッ ピーッ ポーッ ビーッ ファンファーレ
ズバッ ザクッ グサッ ブスッ サクッ ジャキッ シャキーン
メラメラ ボーッ グラグラ ガタガタ バラバラ ポロポロ ボロボロ
ザーザー ポタポタ ポタポタッ シトシト ジメジメ
モクモク ケムリ ボフッ プスーッ スーッ ブワーッ ドバーッ
ガブーッ ズボッ バキューン ドッカーン ゴッカーン パァーン
チチチ ピピピ ピロリン カチカチ パチパチ バチッ
ユラユラ ゆらゆら ヒラヒラ サヤサヤ ショボン ガクッ
コケッ ドテッ バターン ズサッ ゴロッ コロコロ コロンコロ
フラフラ ヨチヨチ ノシノシ ドッスン ズシズシ ガシッ ギュッ
ブチッ パキッ ピキッ ミシミシ ギシギシ キーキー ギャンギャン
ウヘヘ ヒヒヒ フフフ ニチャニチャ ペタペタ ベタベタ
モグモグ ゴクゴク ツルツル パクパク バリバリ ザクザク
ジワジワ ボカッ ボカボカ ドカドカ ゴツン ゴツゴツ
シュワワ ツーン カーッ ボーッ ポーッ クラクラ フラッ
キヨシ ヨシヨシ ナデナデ スリスリ ギュウッ ぎゅっ
ムクッ サッと タッタッ テクテク ノソノソ ウロウロ
キョトン ポカーン ピンと コツン カランカラン チリンチリン
パラパラ バラバラッ ドサドサ ザクザクッ ボトッ ボタッ
シュルシュル ズルル チョキッ パチン ビシッ グサッ
オノマトペ ドンパチ ガチャガチャ ゴチャゴチャ ガタゴト
ゴトゴト ガタンゴトン シャカシャカ チャカチャカ ジャンジャン
""".split()

SFX_KO = """쾅 콰앙 빵야 두둥 쿵 촤악 슥 슉 휘익 끼요오오옥
드르륵 덜컹 철컥 딸깍 따깍 째깍 쏴아아 화아아악 부아아아
우오오오 구오오오 가아아악 크아아아 쿠구구구 웅웅웅
쩝쩝 냠냠 바삭바삭 사각사각 모락모락 잘잘잘 졸졸졸
두근두근 쿵쾅쿵쾅 지끈지끈 욱신욱신 뒤끈뒤끈
훌쩍훌쩍 엉엉 반짝반짝 번쩍 훨훨
콰과아앙 콰직 콰득 지잉잉 웅먕먕 띠링
쨍그랑 따라랑 똑똑 똑딱 쏴앙 촤앙 부웅
발싸 띠용 촥 화르륵 두구두구 쿠쿵쿵
휘파람 삑 삐빅 딩동 짜잔 빙글빙글
스르륵 미끄덩 데굴데굴 두루룩 꿀꺽
슬금슬금 삐걱삐걱 찰칵 찰칵찰칵
또각또각 드드득 쩌우우욱 주르륵
와르르 철렁 부들부들 파닥파닥
훨훌훨 훨훌쩍 싱긋 방긋 씩씩
""".split()

SFX_ZH = """轰 砰 唰 哐当 咔嚓 嗖 呼哧 咚 咣当 噼里啪啦 嘭 哗啦
嗡嗡 吱嘎 咯吱 嘎吱 吧唧 咕噜 咕嘟 咕咚 滴答 哗哗
呼呼 嗷呜 呜哇 嘿呀 哼哼 嘻嘻 哈哈哈 呵呵
哐哐 咚咚 轰隆隆 咔咔 嘎嘣 吧嗒 吧嗒吧嗒
哧溜 呲溜 咻 咻咻 嗡 嗡嗡嗡 叮当 叮铃铃
滋滋 滋啦 噼啪 啪啪 啪叽 咕叽 吧唧吧唧
呜呜 呜呜呜 嘤嘤 嘤 呼噜噜 咕嘟咕嘟
咔嚓咔嚓 咔啦 咯噔 咯噔咯噔 轰隆 轰隆轰隆
""".split()

# ---------------------------------------------------------------- corpus
JUNK_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def _mutate_sfx(w: str, rng: random.Random) -> list:
    out = []
    styles = [
        lambda s: s.upper(),
        lambda s: s[0].upper() + s[1:],
        lambda s: s.upper() + "!",
        lambda s: s.upper() + "!!",
        lambda s: s.upper() + "!!!",
        lambda s: s.upper() + "?!",
        lambda s: s[0] * 3 + s[1:].upper(),
        lambda s: s.upper()[:-1] + s[-1].upper() * 3,
        lambda s: "".join(c * 2 for c in s.upper()),
        lambda s: s.upper() + "-" + s.upper(),
        lambda s: s.upper() + "H",
        lambda s: "K" + s.upper(),
        lambda s: s.upper() + "-BAM",
        lambda s: s.upper() + " " + s.upper() + " " + s.upper(),
        lambda s: "-".join([s.upper()] * 3),
        lambda s: s.upper() + rng.choice(["OOO", "AAA", "HHH"]) * rng.randint(1, 2),
        lambda s: s[0].upper() + "O" * rng.randint(2, 5) + s[1:].upper(),
    ]
    for f in styles:
        try:
            out.append(f(w))
        except Exception:
            pass
    return out

def _load_tatoeba(per_lang: dict, rng: random.Random) -> list:
    """real sentences per language from the local Tatoeba extract"""
    out = []
    for lang, n_max in per_lang.items():
        p = os.path.join(DATA_DIR, f"tatoeba_{lang}.txt")
        if not os.path.isfile(p):
            continue
        lines = [l.strip() for l in open(p, encoding="utf-8") if l.strip()]
        rng.shuffle(lines)
        out.extend(lines[:n_max])
    return out

def _tatoeba_available() -> bool:
    return os.path.isfile(os.path.join(DATA_DIR, "tatoeba_en.txt"))

def build_corpus(verbose: bool = True):
    rng = random.Random(SEED)
    data = []  # (label, text)

    # ---------------- dialogue ----------------
    real = [
        # EN (One Piece colored / Eleceed / Naver page OCR)
        "Wealth, fame, power. Once, there was a man who took everything in this world.",
        "The words he left on the verge of death drove people throughout the world to the sea.",
        "My treasure? If you want it, you can have it...",
        "Search for it! I left everything in the world there.",
        "You think a stunt like that is going to save you?",
        "I never thought I'd see you again.",
        "What are you doing here all alone?",
        "There's no way I'm letting you go.",
        "We should get out of here right now.",
        "Are you serious right now?",
        "That's not what I meant.",
        "You knew about this the whole time?",
        "I don't have time for this.",
        "It's dangerous to go alone.",
        "Everyone, get down!",
        "This is the end of the line.",
        "I've been waiting for this day.",
        "You're the one who started this.",
        "How long are you going to keep this up?",
        "Don't underestimate me!",
        "He's much stronger than we thought.",
        "We have to find the exit before it's too late.",
        "I will never forgive you for this.",
        "So this is the famous academy.",
        "There's something I need to tell you.",
        "It's already too late for that.",
        "Let's finish this once and for all.",
        "You can't stay here anymore.",
        "What happened to your face?",
        "The rumors were true after all.",
        "I knew you would come back.",
        "No one else can know about this.",
        "Where did you get that?",
        "You should be more careful.",
        "This is your last chance.",
        "I'm not the person you think I am.",
        "Everything is going according to plan.",
        "It's too dangerous for a kid.",
        "You did well to make it this far.",
        "From now on, you're on your own.",
        "Huh? What was that sound just now?",
        "Hey, wait up! You're too fast!",
        "No way... that can't be true.",
        "Finally... I found you.",
        "So you've finally awakened.",
        "The door won't open from this side.",
        "This place gives me the creeps.",
        "I told you not to follow me!",
        "You always were the stubborn one.",
        "Is that all you've got?",
        "Ugh... my head is killing me.",
        "What the hell is going on here?",
        "Get out of my way!",
        "I'm begging you, please help me.",
        "You have to believe me.",
        "There's no time to explain.",
        "Just give me one more chance.",
        "Why is this happening to me?",
        "I never asked for any of this.",
        "Are you sure about this?",
        "This isn't what it looks like.",
        "You've gotten a lot stronger.",
        "We meet again at last.",
        "Don't move! Stay right there!",
        "Look out, it's a trap!",
        "I've got your back.",
        "Let's get out of here!",
        "It's now or never!",
        "You saved my life back there.",
        "That was a close one.",
        "I can still fight!",
        "Stay behind me.",
        "Who goes there?!",
        "Halt! Identify yourself!",
        "What business do you have here?",
        "I've been looking everywhere for you.",
        "You're late again.",
        "Can I ask you something?",
        "Mind your own business.",
        "That's none of your concern.",
        "It's better this way.",
        "You'll understand someday.",
        "This is for your own good.",
        "I've made up my mind.",
        "Nothing will stop me now.",
        "The rest is up to you.",
        "Take care of yourself.",
        "Until we meet again.",
        # KO (Naver raw OCR)
        "그래, 여기가 바로 그 곳이야.",
        "뭐가 이렇게 많아?",
        "이건 좀 심하지 않아?",
        "지금이라도 후회해 늦지 않아.",
        "네가 뭘 할 수 있는데?",
        "나를 누구라고 생각하는 거야?",
        "이번 일은 너무 커졌어.",
        "약속은 지켜야지.",
        "그럼 시작해 볼까?",
        "너무 늦기 전에 돌아가자.",
        "형님, 저기가 문제입니다.",
        "얼른 여기서 나가자!",
        "아직 안 끝났어.",
        "다음에 또 보자.",
        "조심해라.",
        # JA
        "お前は誰だ。",
        "そんな馬鹿な…。",
        "ここから出してはらえへん。",
        "待っていたぞ。",
        "これでおしまいだ。",
        "早く逃げろ!",
        "私は負けん!",
        "なんとかなるなるさ。",
        "これは運命かもしれん。",
        "もうあの人には会えない。",
        # ZH
        "你到底是谁？",
        "这里很危险，快走。",
        "我没有时间解释了。",
        "你终于来了。",
        "这是最后的机会。",
        "别小看我！",
        "我们该走了。",
        "这件事就拜托你了。",
        "你不是他要找的人。",
        "一切都会好起来的。",
    ]
    for s in real:
        data.append(("dialogue", s))

    # caps shouts of REAL words — the model must learn that real English
    # words + bangs = dialogue (shout), even in all caps
    shout_words = [
        "stop", "wait", "go", "no", "yes", "why", "how", "who", "what",
        "when", "where", "look", "run", "help", "come", "move", "fire",
        "hold", "listen", "quiet", "enough", "please", "sorry", "thanks",
        "damn", "hell", "die", "stay", "leave", "hide", "duck", "jump",
        "watch", "think", "calm", "hurry", "believe", "understand",
        "remember", "forget", "forgive", "protect", "fight", "win",
        "lose", "save", "kill", "trust", "follow", "escape", "return",
    ]
    for w in shout_words:
        for suf in ["!", "!!", "!!!", "?!", "?", "", "."]:
            data.append(("dialogue", w.upper() + suf))
            data.append(("dialogue", w.capitalize() + suf))
        if rng.random() < 0.3:
            data.append(("dialogue", " ".join([w.upper()] * 2) + "!"))

    # manga-style short cries / interjections (dialogue, NOT sfx)
    short_cries = [
        "No!", "Why?!", "Stop!!", "What?!", "Run!", "Help!!",
        "Look out!", "Behind you!", "Get down!", "Over here!",
        "Not again...", "You're kidding.", "This can't be happening.",
        "I won't lose!", "Watch out!!", "Come on!", "Hurry up!",
        "Shut up!", "As if I'd let you!", "Damn it...", "So it begins.",
        "Now's my chance!", "I can't move!", "It's no use!",
        "Impossible!", "Unbelievable...", "Is everyone alright?",
        "Who's there?!", "Show yourself!", "I'm coming for you!",
        "Please, stop this!", "You'll pay for this!", "Never again.",
        "At last!", "This is it!", "Go for it!", "Do it now!",
        "No way!", "That's insane!", "You liar!", "I knew it!",
        "So strong!", "So fast!", "Too late!", "After them!",
        "Don't move!", "Freeze!", "Drop it!", "Get him!",
        "여긴 어디지?", "빨리 가자!", "말도 안 돼!", "그만해!",
        "무리야...", "잘됐네!", "이제 시작이다!", "큰일났어!",
        "뭐야 그게?", "진짜?", "안 돼!", "어떡해!",
        "やめろ!", "来たか!", "うそだろ…", "行くぞ!",
        "なんだって!?", "馬鹿な!", "逃げろ!", "危ない!",
        "住手！", "快跑！", "不可能！", "交给我吧！",
        "怎么会这样？", "看招！", "小心！", "太强了！",
    ]
    for s in short_cries:
        data.append(("dialogue", s))

    # ---------------- character-profile / stat captions ----------------
    # باکس‌های «نام / سن / نژاد / توانایی» محتوای قابلِ ترجمه‌اند —
    # نه تبلیغ (اشتباهِ رایجِ نسخهٔ قبلی: GLENDA HOLLY AGE: 40 RACE: ...)
    first_names = [
        "Glenda", "Kayla", "Devon", "Aaron", "Abel", "Adrian", "Aiko",
        "Alistair", "Amara", "Amber", "Anya", "Axel", "Beatrice", "Bianca",
        "Blake", "Cain", "Camilla", "Cedric", "Clara", "Damian", "Dante",
        "Daria", "Dominic", "Edgar", "Elena", "Elias", "Emil", "Esther",
        "Ezra", "Felix", "Fiona", "Gareth", "Giselle", "Greta", "Hana",
        "Harold", "Hazel", "Hugo", "Ingrid", "Iris", "Ivan", "Jasmine",
        "Jasper", "Jin", "Kai", "Kira", "Leon", "Lilith", "Luna", "Marcus",
        "Mika", "Nadia", "Nero", "Nina", "Oliver", "Ophelia", "Oscar",
        "Petra", "Quinn", "Raven", "Ren", "Rin", "Rowan", "Ruby", "Sable",
        "Sebastian", "Selene", "Sora", "Stella", "Talia", "Theo", "Trisha",
        "Ursula", "Vera", "Victor", "Violet", "Wendy", "William", "Xander",
        "Yuki", "Yuna", "Zane", "Zoe",
    ]
    surnames = [
        "Holly", "Sommers", "Winters", "Ashford", "Blackwood", "Cruz",
        "Dain", "Elric", "Fairfax", "Grey", "Hale", "Ito", "Johnson",
        "Kang", "Kimura", "Lee", "Lockhart", "Marsh", "Novak", "Okafor",
        "Park", "Quill", "Rivera", "Roth", "Sato", "Sinclair", "Tanaka",
        "Thorne", "Underwood", "Vance", "Voss", "Whitlock", "Yamada",
        "Zhao", "Abernathy", "Bass", "Cole", "Diaz", "Evans", "Frost",
        "Grimaldi", "Hayes", "Irving", "Jang", "Kessler", "Lombardi",
        "Moreau", "Nakamura", "Ortega", "Pemberton", "Rossi", "Sterling",
        "Takahashi", "Vaughn", "Wolfhard", "Young", "Zhang",
    ]
    races = [
        "Human", "Vampire", "Incubus", "Succubus", "Demon", "Elf", "Half-Elf",
        "Beast", "Beastman", "Angel", "Fallen Angel", "Dragon", "Dragonewt",
        "Witch", "Wizard", "Mage", "Ghost", "Reaper", "Alien", "Android",
        "Cyborg", "Mutant", "Slime", "Cat", "Wolf", "Fox Spirit",
        "Kitsune", "Oni", "Dwarf", "Fairy", "Mermaid", "Nekomata",
    ]
    hometowns = [
        "Seoul", "Tokyo", "Osaka", "Busan", "Beijing", "Shanghai", "Norvendia",
        "Alderon", "King's Cross", "The Capital", "North Village",
        "Grand Duchy", "Elmfalls", "Ravenhold", "Sunspire", "Ironvale",
        "Misthollow", "Duskwall", "Frostpeak", "Stormbay",
    ]
    occupations = [
        "Student", "Knight", "Swordmaster", "Mage", "Hunter", "Assassin",
        "Healer", "Merchant", "Detective", "Butler", "Maid", "Teacher",
        "Swordsman", "Archer", "Necromancer", "Alchemist", "Rogue",
        "Noble", "Duke", "Princess", "Bodyguard", "Exorcist",
    ]
    abilities = [
        "Fire Magic", "Ice Magic", "Time Stop", "Telekinesis", "Mind Reading",
        "Shadow Step", "Regeneration", "Blood Control", "Lightning Bolt",
        "Invisibility", "Super Strength", "Flight", "Healing Touch",
        "Beast Taming", "Sword Aura", "Space Manipulation", "Precognition",
    ]

    def _ocr_noise(s: str) -> str:
        if rng.random() < 0.35:
            s = s.replace("O", "0", 1) if "O" in s else s
        if rng.random() < 0.25:
            s = s.replace("l", "1", 1) if "l" in s else s
        if rng.random() < 0.2:
            i = rng.randrange(len(s))
            if s[i].isalpha() and rng.random() < 0.5:
                s = s[:i] + s[i].lower() + s[i + 1:]
        return s

    _profile_templates = [
        "{f} {s} AGE: {a} RACE: {r}",
        "{f} {s} / AGE: {a} / RACE: {r}",
        "NAME: {f} {s} AGE: {a} RACE: {r}",
        "{f} {s} | AGE: {a} | RACE: {r}",
        "{f} {s} — AGE: {a} — RACE: {r}",
        "{f} {s} AGE: {a} RACE: {r} JOB: {o}",
        "{f} {s}, {a}. {r}.",
        "{f} {s} HOMETOWN: {h} RACE: {r}",
        "{f} {s} AGE: {a} OCCUPATION: {o}",
        "{f} {s} • AGE: {a} • RACE: {r}",
        "AGE: {a} / RACE: {r} / JOB: {o}",
        "NAME: {f} {s} / AGE: {a}",
        "{r} — AGE {a} — {o}",
        "{f} {s}  Age: {a}  Race: {r}",
        "{f} {s}  Age: {a}",
        "{f} {s} (Age: {a}, Race: {r})",
    ]
    for _ in range(2600):
        t = _profile_templates[rng.randrange(len(_profile_templates))]
        s = t.format(
            f=rng.choice(first_names), s=rng.choice(surnames),
            a=rng.randint(6, 428), r=rng.choice(races),
            h=rng.choice(hometowns), o=rng.choice(occupations),
        )
        data.append(("dialogue", s))
        if rng.random() < 0.4:
            data.append(("dialogue", _ocr_noise(s)))
        if rng.random() < 0.3:
            data.append(("dialogue", s.upper()))

    # single stat lines — also content
    for _ in range(700):
        pick = rng.randrange(4)
        if pick == 0:
            s = f"AGE: {rng.randint(6, 428)}"
        elif pick == 1:
            s = f"RACE: {rng.choice(races)}"
        elif pick == 2:
            s = f"HOMETOWN: {rng.choice(hometowns)}"
        else:
            s = f"HEIGHT: {rng.randint(140, 210)}CM"
        data.append(("dialogue", s))
        if rng.random() < 0.3:
            data.append(("dialogue", _ocr_noise(s)))

    # ability/skill descriptions — translatable
    _abil_tpl = [
        "SPECIAL ABILITY: {x}", "ABILITY: {x}", "HIS POWER: {x}",
        "HER POWER: {x}", "SKILL: {x}", "HER ABILITY IS {x}.",
        "HIS ABILITY IS {x}.", "THE POWER OF {x}.", "EFFECT: {x}",
    ]
    for _ in range(600):
        t = _abil_tpl[rng.randrange(len(_abil_tpl))]
        s = t.format(x=rng.choice(abilities))
        data.append(("dialogue", s))
        if rng.random() < 0.3:
            data.append(("dialogue", s.upper()))

    # narrator / place / time captions — translatable content
    narrator_caps = [
        "THAT DAY, THE WORLD CHANGED FOREVER.",
        "3 YEARS LATER.", "TWO WEEKS LATER.", "THE NEXT MORNING.",
        "MEANWHILE, AT THE ACADEMY...", "AFTER THE INCIDENT...",
        "BACK THEN...", "AT THE SAME TIME...", "10 YEARS AGO.",
        "ONE HOUR EARLIER.", "THAT NIGHT.", "THE FINAL DAY.",
        "SEOUL, 1998.", "TOKYO, PRESENT DAY.", "THE ROYAL CAPITAL.",
        "SOMEWHERE IN THE NORTH.", "MEANWHILE...", "TO BE CONTINUED...",
        "AT THAT MOMENT.", "IN THE END, EVERYTHING CHANGED.",
        "NO ONE KNEW WHAT WAS COMING.", "IT WAS A QUIET AFTERNOON.",
        "THE STORY BEGINS HERE.", "AND SO, THE JOURNEY STARTED.",
        "그날, 세상이 바뀌었다.", "3년 후.", "그리고 이제.",
        "한편, 그곳에서는.", "그날 밤.", "이야기의 시작.",
        "あの日、世界は変わった。", "3年後。", "翌朝。", "そして今。",
        "那天，世界改变了。", "三年后。", "第二天早上。",
    ]
    for s in narrator_caps:
        data.append(("dialogue", s))
        data.append(("dialogue", s.lower()))
        if rng.random() < 0.4:
            data.append(("dialogue", s.capitalize()))

    # localized profile captions (KO/JA/ZH)
    _ko_names = ["김하늘", "이서준", "박지민", "최유리", "정태양", "한별",
                 "오세림", "남주하", "차도연", "윤그림"]
    _ja_names = ["山田太郎", "佐藤花子", "鈴木一郎", "高橋美咲", "田中健太",
                 "伊藤さくら", "渡辺凛", "中村翔太"]
    _zh_names = ["林小美", "王大明", "张伟", "李小红", "陈建国", "刘芳"]
    for _ in range(400):
        which = rng.randrange(3)
        if which == 0:
            s = (f"이름: {rng.choice(_ko_names)} / 나이: {rng.randint(7, 300)}"
                 f" / 종족: {rng.choice(['인간', '뱀파이어', '마인', '엘프', '수인'])}")
        elif which == 1:
            s = (f"名前：{rng.choice(_ja_names)} / 年齢：{rng.randint(7, 300)}"
                 f" / 種族：{rng.choice(['人間', '吸血鬼', '悪魔', 'エルフ', '獣人'])}")
        else:
            s = (f"姓名：{rng.choice(_zh_names)} / 年龄：{rng.randint(7, 300)}"
                 f" / 种族：{rng.choice(['人类', '吸血鬼', '恶魔', '精灵', '兽人'])}")
        data.append(("dialogue", s))

    # variants of the handmade seeds
    _dlg_seed = [s for lab, s in list(data) if lab == "dialogue"]
    for s in _dlg_seed:
        v = s.replace("...", "…")
        if v != s:
            data.append(("dialogue", v))
        base = s.rstrip(".!?…")
        if s[-1:] in ".!?…":
            data.append(("dialogue", base + "!"))
            data.append(("dialogue", base + "?"))
            data.append(("dialogue", base))
        if s and s[0].islower():
            data.append(("dialogue", s[0].upper() + s[1:]))
        # ALL-CAPS shouting still dialogue when words are real
        if rng.random() < 0.35:
            data.append(("dialogue", "- " + s))
        if rng.random() < 0.2:
            data.append(("dialogue", "「" + s + "」"))
        if rng.random() < 0.2 and s[-1:] == "!":
            data.append(("dialogue", s.upper()))

    # Tatoeba real sentences (the bulk)
    if _tatoeba_available():
        tb = _load_tatoeba({"en": 9000, "ja": 9000, "ko": 6000, "zh": 6000}, rng)
        for s in tb:
            data.append(("dialogue", s))
        if verbose:
            print(f"[*] tatoeba dialogue: {len(tb)}")
    else:
        if verbose:
            print("[!] Tatoeba extracts not found — corpus will be small. "
                  "Run the download step first for best quality.")

    # ---------------- SFX ----------------
    for w in SFX_EN:
        for m in _mutate_sfx(w, rng):
            data.append(("sfx", m))
        # isolated caps form matters most at runtime — add plain + paired
        data.append(("sfx", w.upper()))
        data.append(("sfx", (w.upper() + " " + w.upper())))
    for lst in (SFX_JA, SFX_KO, SFX_ZH):
        for w in lst:
            data.append(("sfx", w))
            data.append(("sfx", w * 2))
            data.append(("sfx", w + "!"))
            data.append(("sfx", w + "ッ"))
            if len(w) >= 2:
                data.append(("sfx", w[0] * 2 + w[1:]))
                data.append(("sfx", w + w[-1] * rng.randint(2, 5)))

    # ---------------- ads / promo / watermark ----------------
    dom = lambda: rng.choice(SITES).replace(" ", "").lower()
    team = lambda: rng.choice(TEAMS)
    handle = lambda: rng.choice(HANDLES)
    tld = lambda: rng.choice(TLDS)
    year = lambda: rng.randint(1994, 2026)
    n = lambda: rng.randint(1, 199)

    templates = []
    for b in ADS_BASE:
        templates += [b, b.capitalize(), b.title(), b + "!", b + ":"]
    # non-English reader-site / scanlation strings
    templates += [
        "汉化", "汉化组", "搬运", "转载请注明出处", "仅供学习交流",
        "禁止用于商业用途", "更多漫画请访问", "汉化组出品", "翻译",
        "校对", "嵌字", "修图", "片源", "快看漫画", "哔哩哔哩漫画",
        "腾讯动漫", "连载中", "每周更新", "扫码阅读", "关注我们",
        "스캔본", "번역", "역자", "PD체", "저작권자", "정식 연재",
        "매주", "업데이트", "완결작", "원작", "작가", "역자님",
        "オフィシャル", "公式", "無断転載禁止", "※この作品はフィクションです",
        "作者", "連載中", "最新刊", "発売中", "好評発売中", "次号掲載",
    ]
    # scanlator credits with real team names
    for role, _x in ROLES_EN:
        templates += [
            f"{role} {team()}", f"{role.upper()} {team()}",
            f"{role} {team()} scans", f"{role}: {team()}",
        ]
    templates += [
        f"{team()}", f"{team()} scans", f"{team()} Scans",
        "team " + team().split()[0].lower(), "credit: " + team(),
        "credits: " + team(), "a " + team() + " production",
        "presented by " + team(), "brought to you by " + team(),
    ]
    # site/domain templates
    for site in SITES:
        s = site.replace(" ", "")
        templates += [
            s, f"{s}.{tld()}", f"www.{s}.{tld()}", f"https://{s}.{tld()}",
            f"read on {s}", f"read on {s}.{tld()}", f"only on {s}",
            f"exclusive on {s}", f"© {s}", f"© {s} {year()}",
            f"©{year()} {s}", f"powered by {s}", f"visit {s}.{tld()}",
        ]
    # socials
    for h in HANDLES:
        templates += [
            f"discord.gg/{h}", f"t.me/{h}", f"twitter.com/{h}",
            f"x.com/{h}", f"instagram.com/{h}", f"facebook.com/{h}",
            f"reddit.com/r/{h}", f"patreon.com/{h}", f"ko-fi.com/{h}",
            f"@{h}", f"follow @{h}", f"join us at discord.gg/{h}",
        ]
    # brands / sponsor-speak
    for b in BRANDS:
        templates += [f"sponsored by {b}", f"brought to you by {b}",
                      f"ad: {b}", f"{b} presents"]
    # chapter headers
    for t in CHAPTER_HEADERS:
        templates += [t.format(n=n()), t.format(n=n()) + "!"]
    templates += END_MARKS
    templates += ["NEW EPISODE", "DAILY PASS", "FREE EPISODE",
                  "UNLOCK NOW", "1 COIN", "10 IMAGES", "SEASON FINALE",
                  "PREVIEW", "NEXT EPISODE PREVIEW"]
    # heavy weight for CJK scanlation/site credit tokens and CTA strings
    for s in ["汉化", "汉化组", "搬运", "翻译", "校对", "嵌字", "修图",
              "汉化组出品", "转载请注明出处", "仅供学习交流",
              "스캔본", "번역", "역자", "저작권자", "정식 연재",
              "無断転載禁止", "公式", "連載中", "最新刊", "発売中"]:
        data.append(("ads", s))
        data.append(("ads", s))
        data.append(("ads", s))
    for s in AD_CTA:
        data.append(("ads", s))
        data.append(("ads", s))
        data.append(("ads", s))
    for t in templates:
        if t and len(t) <= 60:
            data.append(("ads", t))
            if rng.random() < 0.15:
                data.append(("ads", t.upper()))
            if rng.random() < 0.1:
                data.append(("ads", t.lower()))
    # second pass with re-rolled slots — boosts ad recall
    for t in templates:
        if t and len(t) <= 60 and rng.random() < 0.55:
            data.append(("ads", t))
            if rng.random() < 0.2:
                data.append(("ads", t.upper()))

    # ---------------- junk ----------------
    alpha_sets = [
        "abcdefghijklmnopqrstuvwxyz",
        "abcdefghijklmnopqrstuvwxyz0123456789",
        "あいうえおかきくけこさしすせそたちつてとなにぬねの",
        "가나다라마바사아자차카타파하거너더러머버서어저",
        "的一是了我不人在他有这上们来到时大地为子中你说",
    ]
    for _ in range(1400):
        nl = rng.randint(1, 14)
        alpha = rng.choice(alpha_sets)
        s = "".join(rng.choice(alpha) for _ in range(nl))
        if rng.random() < 0.3:
            s += rng.choice(["!", "??", "...", "!!!", "01", "42"])
        data.append(("junk", s))
    for _ in range(300):
        nl = rng.randint(2, 9)
        s = "".join(rng.choice(JUNK_CHARS) for _ in range(nl))
        data.append(("junk", s))
    # symbol-only junk (dots, dashes, stars, boxes…) — OCR noise
    sym_pool = ["!", "?", ".", "…", "—", "–", "-", "_", "~", "*", "#",
                "@", "&", "%", "$", "+", "=", "|", "||", "/", "\\",
                "•", "★", "☆", "※", "°", "♦", "◊", "♪", "∴"]
    for _ in range(500):
        k = rng.randint(1, 8)
        s = "".join(rng.choice(sym_pool) for _ in range(k))
        if rng.random() < 0.25:
            s += rng.choice(["", "!", "?", "..."])
        data.append(("junk", s))
    for s in ["1", "12", "123", "007", "2024", "999+", "3.14", "50%",
              "#@!", "$%^&", "???", "...", "-", "__", "===", "0_O",
              "T_T", "@_@", "^_^", "...?", "!!??", "|", "||", "—",
              "«»", "1O0", "II0I", "0x1F", "____", "......", "•••",
              "!!!!!!", "??????", "......…", "———", "~~~~", "★★★",
              "※※※", "☆☆☆", "::::::", "++++++", "...!", "!!..."]:
        data.append(("junk", s))

    rng.shuffle(data)
    return data

# ---------------------------------------------------------------- train
def train():
    data = build_corpus()
    labels = {l: i for i, l in enumerate(DIM_CLASSES)}
    print(f"[*] corpus: {len(data)} examples")
    from collections import Counter
    cnt = Counter(l for l, _ in data)
    print("[*] per class:", dict(cnt))

    X = [featurize(t) for _, t in data]
    y = np.array([labels[l] for l, _ in data], dtype=np.int64)

    idx = np.random.RandomState(SEED).permutation(len(y))
    n_test = max(1, int(0.15 * len(y)))
    te, tr = idx[:n_test], idx[n_test:]
    Xtr = [X[i] for i in tr]
    Xte = [X[i] for i in te]
    ytr, yte = y[tr], y[te]

    C = len(DIM_CLASSES)
    W = np.zeros((C, B), dtype=np.float32)
    bias = np.zeros(C, dtype=np.float32)
    G = np.ones((C, B), dtype=np.float32)
    Gb = np.ones(C, dtype=np.float32)
    lr, epochs, l2 = 0.3, 16, 1e-6
    bs = 64
    # class weights — balance dialogue against the big junk/sfx pools
    from collections import Counter as _C2
    _cnt = _C2(ytr.tolist())
    _cw = np.array([ (len(ytr) / (C * max(1, _cnt[i]))) ** 0.5
                     for i in range(C) ], dtype=np.float32)
    print("[*] class weights:", dict(zip(DIM_CLASSES, _cw.round(2).tolist())))

    def batch_forward(ix_list):
        """logits for a list of sparse examples"""
        k = len(ix_list)
        uniq = {}
        pairs = []
        for j, (vi, vv) in enumerate(ix_list):
            for a, b in zip(vi.tolist(), vv.tolist()):
                c = uniq.setdefault(a, len(uniq))
                pairs.append((j, c, b))
        nu = len(uniq)
        P = np.zeros((k, nu), dtype=np.float32)
        for j, c, b in pairs:
            P[j, c] = b
        # cols[c] = feature index of column c (insertion order!)
        cols = np.zeros(nu, dtype=np.int64)
        for feat_idx, c in uniq.items():
            cols[c] = feat_idx
        logits = P @ W[:, cols].T + bias
        return logits, P, cols

    for ep in range(epochs):
        rstate = np.random.RandomState(SEED + ep)
        order = rstate.permutation(len(ytr))
        tot_loss = 0.0
        for s in range(0, len(order), bs):
            ix = order[s:s + bs]
            yb = ytr[ix]
            logits, P, cols = batch_forward([Xtr[i] for i in ix])
            logits -= logits.max(axis=1, keepdims=True)
            p = np.exp(logits)
            p /= p.sum(axis=1, keepdims=True)
            k = len(ix)
            tot_loss += (-np.log(p[np.arange(k), yb] + 1e-12)
                         * _cw[yb]).sum()
            d = p
            d[np.arange(k), yb] -= 1.0
            d *= _cw[yb][:, None]      # weighted loss
            dWsub = d.T @ P / k
            db = d.mean(axis=0)
            Wsub = W[:, cols]
            Gsub = G[:, cols]
            Gsub += dWsub * dWsub
            W[:, cols] = Wsub - lr * (dWsub + l2 * Wsub) / np.sqrt(Gsub)
            Gb += db * db
            bias -= lr * db / np.sqrt(Gb)
        print(f"  epoch {ep+1:2d}/{epochs}  loss={tot_loss/len(ytr):.4f}", flush=True)

    def predict_sparse(ix_list):
        logits, _, _ = batch_forward(ix_list)
        return logits.argmax(axis=1)
    pr = predict_sparse(Xte)
    acc = float((pr == yte).mean())
    print(f"[*] test acc: {acc*100:.2f}%  ({len(yte)} examples)")
    conf = np.zeros((C, C), dtype=int)
    for t, p in zip(yte, pr):
        conf[t, p] += 1
    print("[*] confusion (rows=true, cols=pred) order:", DIM_CLASSES)
    print(conf)
    for i, cname in enumerate(DIM_CLASSES):
        tot = conf[i].sum()
        print(f"  {cname:9s} recall = {conf[i, i]/max(1, tot)*100:.1f}%")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    Wq = W.astype(np.float16)
    np.savez_compressed(OUT, W=Wq, bias=bias.astype(np.float32),
                        labels=np.array(DIM_CLASSES),
                        buckets=np.array([B], dtype=np.int64))
    sz = os.path.getsize(OUT) / 1024.0
    print(f"[+] saved {OUT} ({sz:.0f} KB)")

def load_and_predict(text, path=OUT):
    z = np.load(path, allow_pickle=False)
    W = z["W"].astype(np.float32)
    bias = z["bias"]
    labels = [str(x) for x in z["labels"]]
    v = featurize(text, int(z["buckets"][0]), dense=True)
    lg = v @ W.T + bias
    lg -= lg.max()
    p = np.exp(lg)
    p /= p.sum()
    i = int(p.argmax())
    return labels[i], float(p[i])

PROBE = [
    # --- sfx (must be sfx) ---
    "ZWOOSH", "KRA-KOOM!!", "FWOOSH", "THUD", "BAM!!", "SLASH!", "DOOM",
    "VWOOM", "SHAAAH", "KRRRK", "TAK TAK TAK", "BOOM!!!", "CRACK", "KWAAN",
    "ドォン", "ゴゴゴゴ", "バンッ", "ズシャアア", "キラッ", "ドドドド",
    "THUDD", "DAAAN", "GOOON", "BWOOOM", "SKREEE", "KRRK", "THOK",
    "パアアン", "쾅쾅", "咔嚓", "ZZZIP", "SLAM", "POW!!", "CLANG",
    "ドンッ", "ガシャーン", "ズドドド", "KRAKKA", "WOOMPH", "THWIP",
    # --- ads/promo (must be promo) ---
    "Read more at mangadex.org", "SCANLATED BY ZERO SCANS", "Typeset: John",
    "Join our discord server!", "www.webtoons.com", "NAVER WEBTOON",
    "Follow us on twitter @xyz", "Chapter 45: The Beginning",
    "Advertisement", "CLICK HERE", "Powered by Kakao",
    "To be continued...", "SCAN BY FLAME COMICS", "discord.gg/xxxx",
    "MANGADEX.ORG", "Support us on Patreon!", "Chapter 12", "つづく",
    "READ ONLY ON ASURASCANS.COM", "第12話", "Vol.3", "© SHUEISHA",
    "Follow @flamecomics", "Next episode preview", "12화",
    # --- dialogue (must be dialogue) ---
    "I can't believe you did that!", "Are you serious right now?",
    "What happened here?", "Let's get out of this place.",
    "You're lying, aren't you?", "He is the strongest hunter.",
    "STOP!!", "NO!!!", "WHY?!", "GO!", "WAIT!", "HELP US!",
    "그래, 여기가 바로 그 곳이야.", "お前は誰だ。", "你到底是谁？",
    "Don't underestimate me!", "Who's there?!", "This is the end.",
    # --- junk (must be junk) ---
    "12345", "42", "!!!", "......", "0x1F", "#@!", "—", "||",
]

def probe():
    """realistic probe set — prints label+confidence, flags mismatches"""
    bad = 0
    for s in PROBE:
        lab, cf = load_and_predict(s)
        exp = None
        if s in PROBE_SFX: exp = "sfx"
        elif s in PROBE_ADS: exp = "ads"
        elif s in PROBE_DLG: exp = "dialogue"
        elif s in PROBE_JUNK: exp = "junk"
        mark = ""
        if exp is not None and exp != lab:
            mark = "   <<< MISS"
            bad += 1
        print(f"  {cf:.3f} {lab:9s} <- {s!r}{mark}")
    print(f"[*] misses: {bad}/{len(PROBE)}")

PROBE_SFX = {"ZWOOSH", "KRA-KOOM!!", "FWOOSH", "THUD", "BAM!!", "SLASH!",
             "DOOM", "VWOOM", "SHAAAH", "KRRRK", "TAK TAK TAK", "BOOM!!!",
             "CRACK", "KWAAN", "ドォン", "ゴゴゴゴ", "バンッ", "ズシャアア",
             "キラッ", "ドドドド", "THUDD", "DAAAN", "GOOON", "BWOOOM",
             "SKREEE", "KRRK", "THOK", "パアアン", "쾅쾅", "咔嚓", "ZZZIP",
             "SLAM", "POW!!", "CLANG", "ドンッ", "ガシャーン", "ズドドド",
             "KRAKKA", "WOOMPH", "THWIP"}
PROBE_ADS = {"Read more at mangadex.org", "SCANLATED BY ZERO SCANS",
             "Typeset: John", "Join our discord server!", "www.webtoons.com",
             "NAVER WEBTOON", "Follow us on twitter @xyz",
             "Chapter 45: The Beginning", "Advertisement", "CLICK HERE",
             "Powered by Kakao", "To be continued...",
             "SCAN BY FLAME COMICS", "discord.gg/xxxx", "MANGADEX.ORG",
             "Support us on Patreon!", "Chapter 12", "つづく",
             "READ ONLY ON ASURASCANS.COM", "第12話", "Vol.3", "© SHUEISHA",
             "Follow @flamecomics", "Next episode preview", "12화"}
PROBE_DLG = {"I can't believe you did that!", "Are you serious right now?",
             "What happened here?", "Let's get out of this place.",
             "You're lying, aren't you?", "He is the strongest hunter.",
             "STOP!!", "NO!!!", "WHY?!", "GO!", "WAIT!", "HELP US!",
             "그래, 여기가 바로 그 곳이야.", "お前は誰だ。", "你到底是谁？",
             "Don't underestimate me!", "Who's there?!", "This is the end."}
PROBE_JUNK = {"12345", "42", "!!!", "......", "0x1F", "#@!", "—", "||"}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "train":
        train()
        probe()
    elif cmd == "eval":
        for t in sys.argv[2:]:
            lab, cf = load_and_predict(t)
            print(f"  {cf:.3f} {lab:9s} <- {t!r}")
    elif cmd == "probe":
        probe()
