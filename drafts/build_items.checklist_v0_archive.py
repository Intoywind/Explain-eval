import json, sys

# 每个知识点：共用字段 + 两种读者设定（零基础 / 有前置），各自的 learned、not_learned、checklist
# checklist 项写成 (文本, 是否关键项)
KPS = []

def kp(**k):
    KPS.append(k)

# ---------------- ECON1221 ----------------
kp(code="ECON-001", course="ECON1221", knowledge_point="货币市场均衡：利率怎么决定",
   subtype="公式未接含义", source="real:ECON1221-Claude自查#13,#14", difficulty="中",
   request="讲一下货币市场怎么决定利率，讲完我要能做下面这类题。",
   material=("Money demand: Md/P = d0*Y - d1*i (real money demand rises with income Y and falls with the interest rate i).\n"
             "Money supply: the real money supply Ms/P is set by the central bank (exogenous); it does not depend on i.\n"
             "Money market equilibrium: Md/P = Ms/P.\n"
             "Example: Real money demand is Md/P = 0.5Y - 5000i and the real money supply is 600. Output is Y = 1700. "
             "(a) Find the equilibrium interest rate. (b) If the central bank increases the real money supply to 660, "
             "what is the new equilibrium interest rate?"),
   veto=["均衡利率算错（应为 5% 和 3.8%）", "没有回答利率怎么决定"],
   readers={
     "零基础": dict(learned=["需求、供给的一般含义", "解一元一次方程"],
                  not_learned=["货币需求", "货币供给", "利率如何决定", "债券价格与利率的关系"],
                  checklist=[
                    ("先定义货币需求：人们想以现金和活期存款形式持有的钱；说明它随收入上升、随利率下降，并说明随利率下降的原因（拿着钱就放弃了利息）", False),
                    ("先定义货币供给：由央行决定，不随利率变", False),
                    ("说明从题目问法怎么知道要令两者相等：题目问的是 equilibrium interest rate（均衡利率），均衡指的就是货币需求等于货币供给，所以才能把需求式和供给的数值列成等式", True),
                    ("说明两者相等的条件：货币供给由央行固定，利率可以自由变动（央行没有设利率目标），利率会一直调整到人们想持有的钱等于实际有的钱为止", True),
                    ("说明不相等时利率往哪个方向动，以及为什么：比如利率高于均衡时，人们想持有的钱少于实际有的钱，会拿多出来的钱去买债券，债券价格上升、利率随之下降，直到两者相等；利率低于均衡时方向相反", True),
                    ("说明结论怎么用：供给增到 660 时利率降到 3.8%，并说明为什么降", False),
                  ]),
     "有前置": dict(learned=["货币需求函数 Md/P = d0Y − d1i 的含义", "货币供给由央行决定且不随利率变", "解一元一次方程"],
                  not_learned=["货币市场均衡", "债券价格与利率的关系"],
                  checklist=[
                    ("说明从题目问法怎么知道要令两者相等：题目问的是 equilibrium interest rate（均衡利率），均衡指的就是货币需求等于货币供给，所以才能把需求式和供给的数值列成等式", True),
                    ("说明两者相等的条件：货币供给由央行固定，利率可以自由变动（央行没有设利率目标），利率会一直调整到人们想持有的钱等于实际有的钱为止", True),
                    ("说明不相等时利率往哪个方向动，以及为什么：比如利率高于均衡时，人们想持有的钱少于实际有的钱，会拿多出来的钱去买债券，债券价格上升、利率随之下降，直到两者相等；利率低于均衡时方向相反", True),
                    ("说明结论怎么用：供给增到 660 时利率降到 3.8%，并说明为什么降", False),
                  ]),
   })

kp(code="ECON-002", course="ECON1221", knowledge_point="IS 曲线：名字由来与含义",
   subtype="术语未先定义", source="real:ECON1221-Claude自查#11", difficulty="中",
   request="IS 曲线这一节帮我讲一遍。",
   material=("Goods market equilibrium: Y = Z = C + I + G, with C = c0 + c1(Y - T) and I = b0 + b1*Y - b2*i.\n"
             "IS curve: i = (c0 - c1*T + b0 + G)/b2 - ((1 - c1 - b1)/b2) * Y.\n"
             "The IS curve collects all combinations of (Y, i) at which the goods market is in equilibrium. "
             "It is downward sloping. A change in i is a movement along the IS curve; a change in G, T, c0 or b0 shifts it."),
   veto=["IS 的全称或倾斜方向说错"],
   readers={
     "零基础": dict(learned=["一次函数和坐标图", "解一元一次方程"],
                  not_learned=["商品市场均衡", "消费函数", "投资函数", "储蓄", "IS 曲线"],
                  checklist=[
                    ("先说明 C、I、G、T 分别是消费、投资、政府购买、税，以及商品市场均衡 Y = C + I + G 的含义（产出等于对商品的需求）", True),
                    ("解释名称：IS 是 Investment = Saving（投资 = 储蓄），并说明商品市场均衡为什么等价于投资 = 储蓄：可以拆成私人储蓄 Y − T − C 加公共储蓄 T − G，也可以直接写成 I = Y − C − G（国民储蓄），两种都收", True),
                    ("说明曲线上每个点 (Y, i) 的含义：在这个利率下，商品市场均衡时的产出", True),
                    ("说明为什么向右下倾斜：利率升高 → 投资减少 → 需求减少 → 产出减少", False),
                    ("交代向右下倾斜的条件：c1 + b1 < 1 且 b2 > 0，这时斜率 −(1 − c1 − b1)/b2 为负", False),
                    ("说明公式中 c0、c1、b0、b1、b2 各代表什么", False),
                    ("区分沿着曲线移动（只是 i 变）和整条曲线平移（G、T、c0、b0 变）", False),
                  ]),
     "有前置": dict(learned=["商品市场均衡 Y = C + I + G", "消费函数 C = c0 + c1(Y − T)", "投资函数 I = b0 + b1Y − b2i"],
                  not_learned=["储蓄的分解（私人储蓄、公共储蓄）", "IS 曲线"],
                  checklist=[
                    ("解释名称：IS 是 Investment = Saving（投资 = 储蓄），并说明商品市场均衡为什么等价于投资 = 储蓄：可以拆成私人储蓄 Y − T − C 加公共储蓄 T − G，也可以直接写成 I = Y − C − G（国民储蓄），两种都收", True),
                    ("说明曲线上每个点 (Y, i) 的含义：在这个利率下，商品市场均衡时的产出", True),
                    ("说明为什么向右下倾斜：利率升高 → 投资减少 → 需求减少 → 产出减少", False),
                    ("交代向右下倾斜的条件：c1 + b1 < 1 且 b2 > 0，这时斜率 −(1 − c1 − b1)/b2 为负", False),
                    ("区分沿着曲线移动（只是 i 变）和整条曲线平移（G、T、c0、b0 变）", False),
                  ]),
   })

kp(code="ECON-003", course="ECON1221", knowledge_point="乘数 1/(1 − c1 − b1)",
   subtype="公式未接含义", source="real:ECON1221-Claude自查#7,#19", difficulty="中",
   request="常识化、直观化地解释这个公式，我想对它有一个完整的印象。",
   material=("C = c0 + c1(Y - T), I = b0 + b1*Y - b2*i, with the interest rate i fixed.\n"
             "Equilibrium output: Y = 1/(1 - c1 - b1) * (autonomous spending), where autonomous spending = c0 - c1*T + b0 - b2*i + G.\n"
             "Multiplier = 1/(1 - c1 - b1). Change in output: ΔY = Multiplier * Δ(autonomous spending)."),
   veto=["乘数或其条件说错（应为 0 < c1 + b1 < 1 时乘数大于 1）"],
   readers={
     "零基础": dict(learned=["解一元一次方程", "等比数列求和"],
                  not_learned=["边际消费倾向", "自主支出", "均衡产出", "乘数"],
                  checklist=[
                    ("先说明 c1（边际消费倾向）、b1（投资对收入的敏感度）、自主支出（与产出无关的那部分需求）各是什么", True),
                    ("说明公式从哪来：令产出 Y 等于需求，把含 Y 的项移到一边，解出 Y", False),
                    ("说明 1 − c1 − b1 的含义：每多 1 单位产出中，没有再变成需求的那部分比例", True),
                    ("说明乘数为什么大于 1：自主支出增加 ΔA 后，产出增加 ΔA，其中 (c1 + b1)ΔA 又变成需求……逐轮相加得 ΔA/(1 − c1 − b1)，条件是 0 < c1 + b1 < 1", True),
                    ("交代前提：利率固定，所以 b2·i 留在自主支出里不变", False),
                  ]),
     "有前置": dict(learned=["消费函数和投资函数", "令 Y 等于需求解出均衡产出的推导", "等比数列求和"],
                  not_learned=["乘数的直观含义"],
                  checklist=[
                    ("说明 1 − c1 − b1 的含义：每多 1 单位产出中，没有再变成需求的那部分比例", True),
                    ("说明乘数为什么大于 1：自主支出增加 ΔA 后，产出增加 ΔA，其中 (c1 + b1)ΔA 又变成需求……逐轮相加得 ΔA/(1 − c1 − b1)", True),
                    ("区分 1 − c1 − b1 和储蓄：1 − c1 是多 1 单位收入时储蓄增加的部分，再减去 b1 才是没有回到需求里的部分", False),
                    ("交代前提：利率固定，所以 b2·i 留在自主支出里不变", False),
                  ]),
   })

kp(code="ECON-004", course="ECON1221", knowledge_point="公众持有现金时的货币供给",
   subtype="术语未先定义", source="real:ECON1221-Claude自查#24", difficulty="中",
   request="讲一下这道题怎么做。",
   material=("An economy has $2,000 in currency in total, held either by the public or as bank reserves. "
             "Banks hold reserves equal to 10% of deposits. The public holds currency equal to its deposits. "
             "Find public currency, deposits, reserves and the money supply.\n"
             "Relations: M = C + D, B = C + Res, Res = r*D."),
   veto=["四个量有缺或算错（公众现金和存款都约为 1818.18，准备金约为 181.82，货币供给约为 3636.36）"],
   readers={
     "零基础": dict(learned=["解一元一次方程", "百分数"],
                  not_learned=["货币供给", "基础货币", "准备金", "准备金率", "货币乘数"],
                  checklist=[
                    ("先定义基础货币 B：公众手里的现金加上银行的准备金，并说明它和货币供给不是同一个量", True),
                    ("先定义货币供给 M：公众手里的现金加存款，并说明银行准备金不算进 M", True),
                    ("说明本题 C 是现金（不是消费）、D 是存款、r 是准备金率", False),
                    ("说明题目里的 2000 是什么：现金要么在公众手里、要么是银行准备金，所以 2000 = C + Res，也就是基础货币；再用题目给的“公众现金等于存款”“准备金是存款的 10%”把它写成只含存款 D 的关系", False),
                    ("说明这里为什么不能直接用 1/R 乘数：公众留在手里的现金不会再被银行贷出", False),
                  ]),
     "有前置": dict(learned=["准备金和准备金率", "货币乘数 1/R（公众不持有现金时）"],
                  not_learned=["基础货币", "公众持有现金时的货币供给"],
                  checklist=[
                    ("先定义基础货币 B：公众手里的现金加上银行的准备金，并说明它和货币供给不是同一个量", True),
                    ("说明货币供给 M = 公众现金 + 存款，银行准备金不算进 M", True),
                    ("说明题目里的 2000 是什么：现金要么在公众手里、要么是银行准备金，所以 2000 = C + Res，也就是基础货币；再用题目给的“公众现金等于存款”“准备金是存款的 10%”把它写成只含存款 D 的关系", False),
                    ("说明这里为什么不能直接用 1/R 乘数：公众留在手里的现金不会再被银行贷出", False),
                  ]),
   })

kp(code="ECON-005", course="ECON1221", knowledge_point="财政扩张后的产出与消费",
   subtype="切换处漏连接", source="real:ECON1221-Claude自查#17", difficulty="低",
   request="讲一下这道题的解法。",
   material=("Consider a closed economy where C = 100 + 0.6(Y - T), I = 150 + 0.2Y - 1000i, G = 200 and T = 100. "
             "The interest rate is fixed at i = 5%, and equilibrium output is Y = 1700. "
             "Government purchases increase to G = 220. Find the new equilibrium output and the new level of consumption."),
   veto=["新产出或新消费算错（应为 1800 和 1120）"],
   readers={
     "零基础": dict(learned=["代入求值", "解一元一次方程"],
                  not_learned=["消费函数", "可支配收入", "均衡产出", "乘数"],
                  checklist=[
                    ("先说明 C 方程里的 Y − T 是可支配收入（收入减去税），C 是消费", True),
                    ("说明新产出怎么求，两种做法都收：用乘数（政府购买增加 20 是自主支出增加，产出增加它的乘数倍，乘数由 0.6 和 0.2 决定），或把 G = 220 代回 Y = C + I + G 重新解均衡；无论哪种都要说明这一步在求什么", True),
                    ("说明代入消费函数的是可支配收入 Y − T 而不是产出 Y：新产出 1800 要先减去税 100，才是消费函数里用的那个数", True),
                    ("说明消费增加 60 的来源：可支配收入增加 100，乘以 0.6", False),
                    ("交代前提：利率固定在 5%，税 T 不变", False),
                  ]),
     "有前置": dict(learned=["消费函数和可支配收入", "均衡产出和乘数"],
                  not_learned=[],
                  checklist=[
                    ("说明新产出怎么求，两种做法都收：用乘数（政府购买增加 20 是自主支出增加，产出增加它的乘数倍，乘数由 0.6 和 0.2 决定），或把 G = 220 代回 Y = C + I + G 重新解均衡；无论哪种都要说明这一步在求什么", False),
                    ("说明代入消费函数的是可支配收入 Y − T 而不是产出 Y：新产出 1800 要先减去税 100，才是消费函数里用的那个数", True),
                    ("说明消费增加 60 的来源：可支配收入增加 100，乘以 0.6", False),
                    ("交代前提：利率固定在 5%，税 T 不变", False),
                  ]),
   })

# ---------------- COMP2711 ----------------
kp(code="COMP-001", course="COMP2711", knowledge_point="用容斥数满射",
   subtype="前提未交代", source="real:COMP2711-Claude第五轮自查#6,#7", difficulty="高",
   request="讲一下怎么用容斥数满射，讲到我能做下面这种题。",
   material=("The number of onto (surjective) functions from a set of m elements to a set of n elements is "
             "sum_{k=0}^{n} (-1)^k * C(n,k) * (n-k)^m.\n"
             "Example: In how many ways can 5 different tasks be assigned to 3 different servers so that every server gets at least one task?"),
   veto=["例题答案不是 150"],
   readers={
     "零基础": dict(learned=["函数的定义（每个输入恰好对应一个输出）", "组合数 C(n,k)", "乘法原理"],
                  not_learned=["满射", "容斥原理"],
                  checklist=[
                    ("先定义满射：每个输出都至少被一个输入对应到", True),
                    ("说明为什么用容斥：把“每个输出都被用到”转成补集“至少有一个输出没被用到”，再用全部减去", False),
                    ("交代前提：函数允许多个输入对应同一个输出，所以指定 k 个输出不许用时，每个输入独立地有 n − k 种选择，得 (n − k)^m，而不是递减乘积", True),
                    ("说明公式里 k、C(n,k)、(−1)^k 各代表什么", True),
                    ("把例题的每一项和 k 对应起来，说明它在数什么：k = 0 是全部分法，k = 1 是指定某一台服务器空着，k = 2 是指定某两台服务器空着", False),
                    ("说明交集是“至少这 k 个输出没被用到”，不是“恰好”", False),
                  ]),
     "有前置": dict(learned=["函数与满射的定义", "两个和三个集合的容斥公式", "组合数 C(n,k)"],
                  not_learned=["用容斥数满射"],
                  checklist=[
                    ("交代前提：函数允许多个输入对应同一个输出，所以指定 k 个输出不许用时，每个输入独立地有 n − k 种选择，得 (n − k)^m，而不是递减乘积", True),
                    ("说明公式里 k、C(n,k)、(−1)^k 各代表什么", True),
                    ("把例题的每一项和 k 对应起来，说明它在数什么：k = 0 是全部分法，k = 1 是指定某一台服务器空着，k = 2 是指定某两台服务器空着", False),
                    ("说明交集是“至少这 k 个输出没被用到”，不是“恰好”", False),
                  ]),
   })

kp(code="COMP-002", course="COMP2711", knowledge_point="唯一存在 ∃! 的量词写法",
   subtype="切换处漏连接", source="real:COMP2711-Claude cheatsheet自查#7", difficulty="中",
   request="写一条速查表条目：唯一存在怎么用量词写出来，要能看懂。",
   material=("Common mistake: writing ∃x (P(x) → Q(x)) for \"some P is Q\". Translation patterns: \"some P is Q\" is ∃x (P(x) ∧ Q(x)); \"every P is Q\" is ∀x (P(x) → Q(x)).\n"
             "Uniqueness quantifier: ∃!x C(x) ≡ ∃x ( C(x) ∧ ∀z ( C(z) → z = x ) )."),
   veto=["逻辑式写错"],
   readers={
     "零基础": dict(learned=["命题逻辑中 ∧ 和 → 的真值"],
                  not_learned=["量词 ∀ 和 ∃", "唯一存在"],
                  checklist=[
                    ("先说明 ∀（对所有）和 ∃（存在至少一个）的含义", True),
                    ("把式子拆成两半：C(x) 保证有一个满足 C 的 x（存在），∀z(C(z) → z = x) 保证任何满足 C 的对象都是这个 x（唯一）", True),
                    ("说明本式里两个连接词各起什么作用：∧ 要求候选的 x 自己满足 C，同时满足后面的唯一性条件；→ 表示任何满足 C 的 z 都必须等于 x，对不满足 C 的 z 不作要求", True),
                    ("说明 z 是任取的另一个对象，z = x 表示它就是 x", False),
                    ("说明如果去掉前半的 C(x)，会缺什么（x 本身不一定满足 C）", False),
                  ]),
     "有前置": dict(learned=["量词 ∀ 和 ∃ 的含义", "“some P is Q”和“every P is Q”的量词写法"],
                  not_learned=["唯一存在"],
                  checklist=[
                    ("把式子拆成两半：C(x) 保证有一个满足 C 的 x（存在），∀z(C(z) → z = x) 保证任何满足 C 的对象都是这个 x（唯一）", True),
                    ("说明本式里两个连接词各起什么作用：∧ 要求候选的 x 自己满足 C，同时满足后面的唯一性条件；→ 表示任何满足 C 的 z 都必须等于 x，对不满足 C 的 z 不作要求", True),
                    ("说明 z 是任取的另一个对象，z = x 表示它就是 x", False),
                    ("说明如果去掉前半的 C(x)，会缺什么（x 本身不一定满足 C）", False),
                  ]),
   })

kp(code="COMP-003", course="COMP2711", knowledge_point="对角线法证明 (0,1) 不可数",
   subtype="切换处漏连接", source="real:COMP2711-GPT自查C08", difficulty="高",
   request="讲一下用对角线法证明 (0,1) 里的实数不可数。",
   material=("Theorem: The interval (0,1) is uncountable.\n"
             "Proof (Cantor's diagonal argument): Suppose r1, r2, r3, ... is a list of all real numbers in (0,1). "
             "Write r_n = 0.d_n1 d_n2 d_n3 ... in decimal, choosing the expansion that does not end in infinitely many 9s. "
             "Construct s = 0.s1 s2 s3 ... where s_n = 4 if d_nn ≠ 4, and s_n = 5 if d_nn = 4. "
             "Then s is in (0,1) but differs from every r_n. Contradiction."),
   veto=["结论说错，或构造出的 s 不能保证和每个 r_n 都不同"],
   readers={
     "零基础": dict(learned=["小数表示", "反证法"],
                  not_learned=["可数", "一一对应", "对角线法"],
                  checklist=[
                    ("先定义可数：能和自然数一一配对，也就是能排成一份完整的编号列表", True),
                    ("先说明证明目标：任何一份声称完整的列表都会漏掉某个数；所以先假设有一份完整列表，再找出它漏掉的数", True),
                    ("说明构造 s 的规则怎样保证 s 和列表里每一个数都不同：对任意第 n 个数 r_n，s 的第 n 位和 r_n 的第 n 位不同，所以 s ≠ r_n；其他能做到这一点的构造也收", True),
                    ("说明为什么选的数字要避开 0 和 9（本题用 4 和 5）、为什么不用以无限个 9 结尾的写法：避免同一个数有两种小数写法；换成其他避开 0 和 9 的数字也成立", False),
                    ("说明论证对任意列表都成立，示例列表只是演示", False),
                    ("收束：s 在 (0,1) 里却不在列表里，和“列表完整”矛盾，所以不可数", False),
                  ]),
     "有前置": dict(learned=["可数的定义（能和自然数一一配对）", "反证法"],
                  not_learned=["对角线法"],
                  checklist=[
                    ("先说明证明目标：任何一份声称完整的列表都会漏掉某个数；所以先假设有一份完整列表，再找出它漏掉的数", True),
                    ("说明构造 s 的规则怎样保证 s 和列表里每一个数都不同：对任意第 n 个数 r_n，s 的第 n 位和 r_n 的第 n 位不同，所以 s ≠ r_n；其他能做到这一点的构造也收", True),
                    ("说明为什么选的数字要避开 0 和 9（本题用 4 和 5）、为什么不用以无限个 9 结尾的写法：避免同一个数有两种小数写法；换成其他避开 0 和 9 的数字也成立", False),
                    ("说明论证对任意列表都成立，示例列表只是演示", False),
                    ("收束：s 在 (0,1) 里却不在列表里，和“列表完整”矛盾，所以不可数", False),
                  ]),
   })

kp(code="COMP-004", course="COMP2711", knowledge_point="量词移动为什么要求论域非空",
   subtype="前提未交代", source="real:COMP2711-GPT自查C04", difficulty="中",
   request="这条等价为什么要求论域非空？我没看懂。",
   material=("Equivalence (A does not contain x): A ∨ ∃x P(x) ≡ ∃x (A ∨ P(x)). This holds when the domain is nonempty.\n"
             "On an empty domain, ∀x P(x) is true and ∃x P(x) is false."),
   veto=["空论域上 ∀、∃ 的真值说反"],
   readers={
     "零基础": dict(learned=["∨ 的真值", "∀ 和 ∃ 的含义"],
                  not_learned=["空论域上量词的真值", "量词移动的条件"],
                  checklist=[
                    ("说明空论域上 ∃xP(x) 为假的原因：找不到任何满足的对象", True),
                    ("代入反例：空论域且 A 为真时，左边 A ∨ ∃xP(x) 为真；右边 ∃x(A ∨ P(x)) 要找到一个 x，空论域里没有，所以为假", True),
                    ("交代另一个前提：A 里不含 x", False),
                    ("说明论域非空时两边为什么等价：A 为真时任取一个对象就能让右边成立", False),
                  ]),
     "有前置": dict(learned=["∀ 和 ∃ 的含义", "空论域上 ∀ 为真而 ∃ 为假，以及原因"],
                  not_learned=["量词移动的条件"],
                  checklist=[
                    ("代入反例：空论域且 A 为真时，左边 A ∨ ∃xP(x) 为真；右边 ∃x(A ∨ P(x)) 要找到一个 x，空论域里没有，所以为假", True),
                    ("交代另一个前提：A 里不含 x", False),
                    ("说明论域非空时两边为什么等价：A 为真时任取一个对象就能让右边成立", False),
                  ]),
   })

kp(code="COMP-005", course="COMP2711", knowledge_point="期望的线性性",
   subtype="术语未先定义", source="real:COMP2711-Claude cheatsheet自查#1,#6", difficulty="低",
   request="给这条公式写一条速查表条目：先给公式，再说它一般用来做什么，再解释公式里的符号代表什么，中学生也要能看懂。",
   material=("Linearity of expectation: E[aX + bY + c] = a*E[X] + b*E[Y] + c. "
             "In this course X and Y take finitely many values, and then this holds for any such X and Y, whether or not they are independent."),
   veto=["说成需要独立才成立"],
   readers={
     "零基础": dict(learned=["概率", "加权平均"],
                  not_learned=["随机变量", "期望"],
                  checklist=[
                    ("说明 X、Y 是随机变量：给每个可能结果对应一个数", True),
                    ("说明 E[X] 是什么、怎么算：每个取值乘它的概率再相加", True),
                    ("说明 a、b、c 是固定的常数，和随不同结果变化的 X、Y 不同", True),
                    ("说明公式一般用来做什么：把复杂量的期望拆成几个简单量的期望再相加", False),
                    ("说明为什么不需要独立：在每个结果上先把数加起来再求平均，和分别求平均再相加一样", False),
                  ]),
     "有前置": dict(learned=["随机变量", "期望的定义和计算"],
                  not_learned=["期望的线性性"],
                  checklist=[
                    ("解释公式里的符号：X、Y 是随机变量，E 表示期望（可以简短，读者已学过）", False),
                    ("说明 a、b、c 是固定的常数，和随不同结果变化的 X、Y 不同", True),
                    ("说明公式一般用来做什么：把复杂量的期望拆成几个简单量的期望再相加", False),
                    ("说明为什么不需要独立：在每个结果上先把数加起来再求平均，和分别求平均再相加一样", True),
                  ]),
   })

# ---------------- IEDA1280 ----------------
kp(code="IEDA-001", course="IEDA1280", knowledge_point="经济订货量 EOQ",
   subtype="公式未接含义", source="real:IEDA1280-GPT第三轮自查#01,#03", difficulty="中",
   request="把这两个公式讲成中文逻辑：在算什么、为什么这样乘除、结果用在哪一步。",
   material=("EOQ assumptions: single product; known and constant demand rate; instantaneous replenishment; no shortage; no quantity discounts.\n"
             "Annual relevant cost: C(Q) = (D/Q)*S + (Q/2)*H.\n"
             "Economic order quantity: Q* = sqrt(2DS/H)."),
   veto=["公式写错"],
   readers={
     "零基础": dict(learned=["平方根", "平均数"],
                  not_learned=["订货成本", "持有成本", "EOQ"],
                  checklist=[
                    ("逐一说明 D、Q、S、H 的含义和单位", True),
                    ("说明 D/Q 是一年下单次数、Q/2 是平均库存，并说明平均库存为什么是 Q/2（每批从 Q 均匀用到 0）", True),
                    ("说明 C(Q) 的两项此消彼长：Q 越大，订货费越少、持有费越多", False),
                    ("说明 Q* 的来由：先讲清为什么两项相等处总费用最低（求导令导数为 0、两项乘积 DS·H/2 是定值所以相等时和最小、或边际分析，任一种讲清楚都收），再由 DS/Q = HQ/2 得到 Q² = 2DS/H，交代 2 和开平方各从哪里来", True),
                    ("交代适用前提：需求已知且恒定、即时补货、不缺货、无数量折扣", False),
                    ("说明结果用来做什么：Q* 是每次订多少，Q/D 是订货间隔；只许整数时比较相邻两个整数的费用", False),
                  ]),
     "有前置": dict(learned=["订货成本和持有成本的含义", "D、S、H 各自的含义和单位"],
                  not_learned=["EOQ 公式的来由"],
                  checklist=[
                    ("说明 D/Q 是一年下单次数、Q/2 是平均库存，并说明平均库存为什么是 Q/2（每批从 Q 均匀用到 0）", True),
                    ("说明 C(Q) 的两项此消彼长：Q 越大，订货费越少、持有费越多", False),
                    ("说明 Q* 的来由：先讲清为什么两项相等处总费用最低（求导令导数为 0、两项乘积 DS·H/2 是定值所以相等时和最小、或边际分析，任一种讲清楚都收），再由 DS/Q = HQ/2 得到 Q² = 2DS/H，交代 2 和开平方各从哪里来", True),
                    ("说明结果用来做什么：Q* 是每次订多少，Q/D 是订货间隔；只许整数时比较相邻两个整数的费用", False),
                  ]),
   })

kp(code="IEDA-002", course="IEDA1280", knowledge_point="交货期超过订货周期时的再订货点",
   subtype="前提未交代", source="real:IEDA1280-GPT第三轮自查#05", difficulty="高",
   request="讲这道题，两种交货期都要讲。",
   material=("Annual demand D = 500 units, order quantity Q = 25 units, 52 weeks per year. "
             "Find the reorder point (ROP), defined as the on-hand inventory level at which a new order is placed, when the lead time is (a) L = 2 weeks and (b) L = 6 weeks."),
   veto=["再订货点算错（应约为 19.23 件和 7.69 件）"],
   readers={
     "零基础": dict(learned=["单位换算", "除法"],
                  not_learned=["交货提前期", "订货周期", "再订货点", "在途订单"],
                  checklist=[
                    ("先定义交货提前期 L（下单到到货的等待时间）和订货周期 T = Q/D（两次下单的间隔），并说明两者不同", True),
                    ("定义再订货点：手头库存降到多少件时下单", False),
                    ("说明 L = 2 周小于 T = 2.6 周时，等待期间不会有旧订单到货，只能靠手头库存，所以再订货点就是等待期间的用量", False),
                    ("L = 6 周 > T：交代前提，等待期间会有以前下的订单陆续到货，所以要先看 6 周里包含几个完整的订货周期", True),
                    ("展开时间线：两张旧订单分别在第 −5.2 周和第 −2.6 周下单，加 6 周后在第 0.8 周和第 3.4 周到货，所以手头只需撑 0.8 周", True),
                    ("说明这个结果依赖持续补货：第一次开店没有在途订单，不能照套", False),
                  ]),
     "有前置": dict(learned=["交货提前期和订货周期", "L ≤ T 时 ROP = D × L"],
                  not_learned=["L > T 时的再订货点"],
                  checklist=[
                    ("L = 6 周 > T：交代前提，等待期间会有以前下的订单陆续到货，所以要先看 6 周里包含几个完整的订货周期", True),
                    ("展开时间线：两张旧订单分别在第 −5.2 周和第 −2.6 周下单，加 6 周后在第 0.8 周和第 3.4 周到货，所以手头只需撑 0.8 周", True),
                    ("说明这个结果依赖持续补货：第一次开店没有在途订单，不能照套", False),
                  ]),
   })

kp(code="IEDA-003", course="IEDA1280", knowledge_point="报童模型的临界比率",
   subtype="公式未接含义", source="real:IEDA1280-GPT第三轮自查#07", difficulty="高",
   request="这个临界比率怎么理解？并用这组数据求最优备货量。",
   material=("Rocky pays $0.5 for each paper and sells it for $1.5. Unsold papers are worthless at the end of the day.\n"
             "Daily demand: 87 (0.03), 88 (0.07), 89 (0.2), 90 (0.4), 91 (0.2), 92 (0.07), 93 (0.03).\n"
             "Critical ratio CR = Cu / (Cu + Co). Stock the smallest Q such that F(Q) ≥ CR, where F(Q) = P(demand ≤ Q)."),
   veto=["最优备货量不是 90 份"],
   readers={
     "零基础": dict(learned=["概率", "累计概率"],
                  not_learned=["报童模型", "少订损失 Cu", "多订损失 Co", "边际分析"],
                  checklist=[
                    ("先定义 Cu（少备一份损失的利润）和 Co（多备一份卖不掉的损失），本题 Cu = 1.5 − 0.5 = 1，Co = 0.5", True),
                    ("说明 F(Q) 的含义：备 Q 份时当天够卖的概率", False),
                    ("边际分析：多备第 Q + 1 份，有 F(Q) 的概率卖不掉、损失 Co，有 1 − F(Q) 的概率卖掉、多赚 Cu", True),
                    ("推出门槛：多备一份划算等价于 F(Q) < Cu/(Cu + Co)，所以临界比率是“再加一份还划不划算”的分界", True),
                    ("说明为什么取第一个使 F(Q) ≥ 2/3 的备货量：在它之前每多备一份都划算，到它为止再多备就不划算了", False),
                    ("交代前提：剩报没有残值，也没有额外处理费", False),
                  ]),
     "有前置": dict(learned=["报童模型是什么", "Cu 和 Co 的定义", "累计概率"],
                  not_learned=["临界比率的来由"],
                  checklist=[
                    ("边际分析：多备第 Q + 1 份，有 F(Q) 的概率卖不掉、损失 Co，有 1 − F(Q) 的概率卖掉、多赚 Cu", True),
                    ("推出门槛：多备一份划算等价于 F(Q) < Cu/(Cu + Co)，所以临界比率是“再加一份还划不划算”的分界", True),
                    ("说明为什么取第一个使 F(Q) ≥ 2/3 的备货量：在它之前每多备一份都划算，到它为止再多备就不划算了", False),
                  ]),
   })

kp(code="IEDA-004", course="IEDA1280", knowledge_point="集合覆盖的贪心启发式",
   subtype="切换处漏连接", source="real:IEDA1280-GPT第二轮自查#03,#08", difficulty="中",
   request="讲一下 (b) 和 (c)。",
   material=("Six zones (1)-(6) must each be covered by at least one 5G tower. Candidate tower sites [1]-[6] cover:\n"
             "[1] -> {1,3}; [2] -> {1,2,4}; [3] -> {1,4,5}; [4] -> {2,6}; [5] -> {3,5}; [6] -> {4,5,6}.\n"
             "Annual costs (in $100,000): [1] 14, [2] 19, [3] 24, [4] 16, [5] 25, [6] 21.\n"
             "(b) Solve the set covering model by the greedy heuristic (at each step, choose the site with the lowest cost per newly covered zone), and find the total annual cost in this solution.\n"
             "(c) Someone claims that the solution in (b) is suboptimal. Do you agree? Explain your answer."),
   veto=["贪心方案或总成本算错（应选 [2][6][1]，成本 54）"],
   readers={
     "零基础": dict(learned=["除法和比较大小"],
                  not_learned=["集合覆盖", "贪心启发式", "可行解与最优解"],
                  checklist=[
                    ("说明贪心每一轮比较什么：c_j/d_j，即每新增覆盖一个区域要花多少；d_j 是该地点在还没被覆盖的区域里能新增覆盖几个", True),
                    ("说明为什么每轮要重新算 d_j（已经被覆盖的区域不再算），并在第二轮 [6] 从 3 个降到 2 个的地方写出来", True),
                    ("(c) 给出一个同样覆盖全部六个区、费用更低的具体方案，并逐区核对它确实全覆盖（如 [1][4][6] 覆盖 {1,3}、{2,6}、{4,5,6}，成本 51 < 54）；说明有一个这样的方案就足以证明 (b) 不是最优，不需要再证明它是最低", True),
                    ("解释为什么每轮最划算不保证总费用最低：贪心只看当前比率、不比较组合，先选的 [2] 和后选的塔覆盖重叠", True),
                    ("区分可行解（全部覆盖）和最优解（没有更便宜的可行方案）", False),
                  ]),
     "有前置": dict(learned=["集合覆盖模型", "可行解与最优解"],
                  not_learned=["贪心启发式"],
                  checklist=[
                    ("说明贪心每一轮比较什么：c_j/d_j，即每新增覆盖一个区域要花多少；d_j 是该地点在还没被覆盖的区域里能新增覆盖几个", False),
                    ("说明为什么每轮要重新算 d_j（已经被覆盖的区域不再算），并在第二轮 [6] 从 3 个降到 2 个的地方写出来", True),
                    ("(c) 给出一个同样覆盖全部六个区、费用更低的具体方案，并逐区核对它确实全覆盖（如 [1][4][6] 覆盖 {1,3}、{2,6}、{4,5,6}，成本 51 < 54）；说明有一个这样的方案就足以证明 (b) 不是最优，不需要再证明它是最低", True),
                    ("解释为什么每轮最划算不保证总费用最低：贪心只看当前比率、不比较组合，先选的 [2] 和后选的塔覆盖重叠", True),
                  ]),
   })

kp(code="IEDA-005", course="IEDA1280", knowledge_point="报童模型适用于哪类商品",
   subtype="术语未先定义", source="real:IEDA1280-GPT第三轮自查#06", difficulty="低",
   request="讲一下这道选择题。",
   material=("Which of these products would be most apt to involve the use of a newsboy model?\n"
             "A) gold coins  B) hammers  C) fresh fish  D) calculators  E) frozen corn"),
   veto=["答案不是 C"],
   readers={
     "零基础": dict(learned=[],
                  not_learned=["报童模型", "单期备货", "残值"],
                  checklist=[
                    ("先说明报童模型是什么：只有一次订货机会、需求不确定、期末卖不完的货会贬值，要决定备多少", True),
                    ("说明判断依据：销售期结束后，剩下的货价值是否大幅下降", True),
                    ("说明为什么鲜鱼最符合单期备货：当天卖不完就大幅贬值；其余选项都能存到下一期再卖，可以归在一起讲，不必逐个讲", False),
                    ("给出答案 C", False),
                  ]),
     "有前置": dict(learned=["报童模型的定义"],
                  not_learned=["怎样判断题目里的商品适不适用报童模型"],
                  checklist=[
                    ("说明判断依据：销售期结束后，剩下的货价值是否大幅下降", True),
                    ("说明为什么鲜鱼最符合单期备货：当天卖不完就大幅贬值；其余选项都能存到下一期再卖，可以归在一起讲，不必逐个讲", False),
                    ("给出答案 C", False),
                  ]),
   })

def build():
    rows = []
    for k in KPS:
        for label, r in k["readers"].items():
            rows.append(dict(
                id=f'{k["code"]}-{label}', course=k["course"], knowledge_point=k["knowledge_point"],
                subtype=k["subtype"], source=k["source"], difficulty=k["difficulty"],
                reader_known=dict(learned=r["learned"], not_learned=r["not_learned"]),
                request=k["request"], material=k["material"],
                checklist=[dict(id=f"c{i+1}", text=t, key=key) for i, (t, key) in enumerate(r["checklist"])],
                veto=k["veto"], split="dev"))
    return rows

if __name__ == "__main__":
    rows = build()
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows))
