#!/usr/bin/env python3
"""Text filter — tiny char-ngram softmax classifier (pure numpy).

Trains on a data-driven corpus (dialogue / sfx / ads / junk) and exports
models/text_filter.npz. Runtime inference needs ONLY numpy — no fasttext,
no onnxruntime — so it runs on PC, Web and Android (Chaquopy) alike.

The classification «rules» live in the TRAINING DATA, not in engine code:
the model learns SFX/ads/junk patterns from labeled examples.

Usage:
  python3 tools/text_filter.py train            # build corpus + train + eval
  python3 tools/text_filter.py eval "BOOOM!!!"  # quick test
"""
import os, sys, re, math, json, random, unicodedata
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "models", "text_filter.npz")
B = 1 << 18          # hash buckets
DIM_CLASSES = ["dialogue", "sfx", "ads", "junk"]
SEED = 137

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
    val = np.fromiter(counts.values(), dtype=np.float32, count=len(counts))
    np.sqrt(val, out=val)
    n = float(np.linalg.norm(val))
    if n > 0:
        val /= n
    if dense:
        v = np.zeros(buckets, dtype=np.float32)
        v[idx] = val
        return v
    return idx, val

# ---------------------------------------------------------------- corpus
SFX_EN = """boom bam pow zap wham crash bang clang thud slam smash crack
crunch snap pop fizz buzz hum ring chime ding dong beep boop honk vroom
zoom whoosh swoosh swish whip slash slice stab pierce shing clank clink
thump thwack biff sock punch kick jab rumble roar growl hiss
bark howl whimper yelp shriek screech squeak creak groan moan sigh
gasp pant wheeze cough sniff sob blub drip splash sploosh slosh gurgle
gulp slurp chomp munch nibble chew burp hiccup yawn sniffle
flutter flap swish rustle crackle sizzle fizzle
kaboom kapow boosh fwoosh shwoosh krakk krrsh shaaah hwaaah
""".split()

SFX_JA = """ドン バン ゴゴゴ ザアア ドダダ ガタガタ ガシャン バキッ ボカッ
ゴキッ メキッ ズシッ ドカン バアアン キラキラ ピカッ カチッ パチッ
サッ シュッ ヒュウ ビュウ ザッ ワアワア ウワアア ギャアア ウォアア
ドクドク バクバク ズキズキ キリキリ ジリジリ ムカムカ イライラ
ペコペコ キョロキョロ ジロジロ ニヤニヤ ウフフ アハハ オホホ
エヘヘ ウシシ ケケケ ガハハ ニャア ワン モー メー コケコッ
チュンチュン カアカア ケロケロ ブンブン ザンザン カラン コロン
""".split()

SFX_KO = """쾅 빵야 두둥 쿵 촤악 슥 슉 휘익 끼요오오옥
드르륵 덜컹 철컥 딸깍 따깍 째깍 쏴아아 화아아악 부아아아
우오오오 구오오오 가아아악 크아아아 쿠구구구 웅웅웅
쩝쩝 냠냠 바삭바삭 사각사각 모락모락 잘잘잘 졸졸졸
두근두근 쿵쾅쿵쾅 지끈지끈 욱신욱신 뒤끈뒤끈
훌쩍훌쩍 엉엉 반짝반짝 번쩍 훨훨
""".split()

SFX_ZH = """轰 砰 唰 哐当 咔嚓 嗖 呼哧 咚 咣当 噼里啪啦 嘭 哗啦
嗡嗡 吱嘎 咯吱 嘎吱 吧唧 咕噜 咕嘟 咕咚 滴答 哗哗
呼呼 嗷呜 呜哇 嘿呀 哼哼 嘻嘻 哈哈哈 呵呵
""".split()

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
]

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
    ]
    for f in styles:
        out.append(f(w))
    if len(w) >= 2:
        out.append(w.upper()[0] + "O" * rng.randint(2, 5) + w.upper()[1:] + "!")
        out.append(w.upper() + rng.choice(["OOO", "AAA", "HHH"]) * rng.randint(1, 2))
    return out

def build_corpus():
    rng = random.Random(SEED)
    data = []  # (label, text)

    # --- dialogue: real OCR lines from the project's own test pages ---
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

    # dialogue variants: light punct/ellipsis/case changes
    _dlg_seed = [s for lab, s in list(data) if lab == "dialogue"]
    for s in _dlg_seed:
        v = s.replace("...", "…")
        if v != s:
            data.append(("dialogue", v))
        if s.endswith("."):
            data.append(("dialogue", s[:-1] + "!"))
            data.append(("dialogue", s[:-1] + "?"))
            data.append(("dialogue", s[:-1]))
        if s and s[0].islower():
            data.append(("dialogue", s[0].upper() + s[1:]))
        if rng.random() < 0.5:
            data.append(("dialogue", "- " + s))
        if rng.random() < 0.3:
            data.append(("dialogue", "「" + s + "」"))
    # short interjections common in manga
    for s in ["No!", "Why?!", "Stop!!", "What?!", "Run!", "Help!!",
              "Look out!", "Behind you!", "Get down!", "Over here!",
              "Not again...", "You're kidding.", "This can't be happening.",
              "I won't lose!", "Watch out!!", "Come on!", "Hurry up!",
              "Shut up!", "As if I'd let you!", "Damn it...", "So it begins.",
              "Now's my chance!", "I can't move!", "It's no use!",
              "Impossible!", "Unbelievable...", "Is everyone alright?",
              "Who's there?!", "Show yourself!", "I'm coming for you!",
              "Please, stop this!", "You'll pay for this!", "Never again.",
              "At last!", "This is it!", "Go for it!", "Do it now!",
              "여긴 어디지?", "빨리 가자!", "말도 안 돼!", "그만해!",
              "무리야...", "잘됐네!", "이제 시작이다!",
              "やめろ!", "来たか!", "うそだろ…", "行くぞ!",
              "住手！", "快跑！", "不可能！", "交给我吧！"]:
        data.append(("dialogue", s))

    # --- SFX ---
    for w in SFX_EN:
        for m in _mutate_sfx(w, rng):
            data.append(("sfx", m))
    for lst in (SFX_JA, SFX_KO, SFX_ZH):
        for w in lst:
            data.append(("sfx", w))
            data.append(("sfx", w * 2))
            data.append(("sfx", w + "!"))
            if len(w) >= 2:
                data.append(("sfx", w[0] * 2 + w[1:]))

    # --- ads / promo / watermark ---
    slots = ["MangaPlus", "WebtoonHub", "MangaDex", "ScanZone", "ToonVerse",
             "RawKuna", "ManhuaPlus", "ComicK", "Asura", "Bato",
             "Naver Series", "KakaoPage", "Tappytoon", "Lezhin"]
    for b in ADS_BASE:
        data.append(("ads", b))
        data.append(("ads", b.capitalize()))
        data.append(("ads", b + " " + rng.choice(slots)))
        data.append(("ads", rng.choice(slots) + ".com"))
        data.append(("ads", "© " + rng.choice(slots)))
        data.append(("ads", b + "!"))
    for extra in ["CHAPTER 12", "Chapter 24", "EP 5", "Episode 108",
                  "第12話", "12화", "제1화", "第104章", "Vol.3", "END",
                  "To be continued", "つづく", "다음 화에 계속", "下集待續",
                  "Fin.", "おわり", "The End", "완결"]:
        data.append(("ads", extra))

    # --- junk: random strings, mash, digits ---
    alpha_sets = [
        "abcdefghijklmnopqrstuvwxyz",
        "abcdefghijklmnopqrstuvwxyz0123456789",
        "あいうえおかきくけこさしすせそたちつてとなにぬねの",
        "가나다라마바사아자차카타파하거너더러머버서어저",
        "的一是了我不人在他有这上们来到时大地为子中你说",
    ]
    for _ in range(1400):
        n = rng.randint(1, 14)
        alpha = rng.choice(alpha_sets)
        s = "".join(rng.choice(alpha) for _ in range(n))
        if rng.random() < 0.3:
            s += rng.choice(["!", "??", "...", "!!!", "01", "42"])
        data.append(("junk", s))
    for _ in range(300):
        n = rng.randint(2, 9)
        s = "".join(rng.choice(JUNK_CHARS) for _ in range(n))
        data.append(("junk", s))
    for s in ["1", "12", "123", "007", "2024", "999+", "3.14", "50%",
              "#@!", "$%^&", "???", "...", "-", "__", "===", "0_O",
              "T_T", "@_@", "^_^", "...?", "!!??"]:
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
    lr, epochs, l2 = 0.3, 28, 1e-6
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

def load_and_predict(text):
    z = np.load(OUT, allow_pickle=False)
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

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "train":
        train()
    elif cmd == "eval":
        for t in sys.argv[2:]:
            lab, cf = load_and_predict(t)
            print(f"  {cf:.3f} {lab:9s} <- {t!r}")
