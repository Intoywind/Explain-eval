import json, sys

# 条目的唯一来源。改条目只改这个文件，再重新生成 jsonl，不要直接改 jsonl。
# 每个知识点：共用字段 + 两种读者设定（零基础 / 有前置）。
# 判分用的卡点问题（QUESTIONS）和推荐步骤（STEPS）写在文件后半，按知识点编号对应。
# knowledge_errors：知识错误（答案或结论错），单独计数，不和跳步混在一起。
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
   knowledge_errors=["均衡利率算错（应为 5% 和 3.8%）"],
   readers={
     "零基础": dict(learned=["需求、供给的一般含义", "解一元一次方程"],
                  not_learned=["货币需求", "货币供给", "利率如何决定", "债券价格与利率的关系"]),
     "有前置": dict(learned=["货币需求函数 Md/P = d0Y − d1i 的含义", "货币供给由央行决定且不随利率变", "解一元一次方程"],
                  not_learned=["货币市场均衡", "债券价格与利率的关系"]),
   })

kp(code="ECON-002", course="ECON1221", knowledge_point="IS 曲线：名字由来与含义",
   subtype="术语未先定义", source="real:ECON1221-Claude自查#11", difficulty="中",
   request="IS 曲线这一节帮我讲一遍。",
   material=("Goods market equilibrium: Y = Z = C + I + G, with C = c0 + c1(Y - T) and I = b0 + b1*Y - b2*i.\n"
             "IS curve: i = (c0 - c1*T + b0 + G)/b2 - ((1 - c1 - b1)/b2) * Y.\n"
             "The IS curve collects all combinations of (Y, i) at which the goods market is in equilibrium. "
             "It is downward sloping. A change in i is a movement along the IS curve; a change in G, T, c0 or b0 shifts it."),
   knowledge_errors=["IS 的全称或倾斜方向说错"],
   readers={
     "零基础": dict(learned=["一次函数和坐标图", "解一元一次方程"],
                  not_learned=["商品市场均衡", "消费函数", "投资函数", "储蓄", "IS 曲线"]),
     "有前置": dict(learned=["商品市场均衡 Y = C + I + G", "消费函数 C = c0 + c1(Y − T)", "投资函数 I = b0 + b1Y − b2i"],
                  not_learned=["储蓄的分解（私人储蓄、公共储蓄）", "IS 曲线"]),
   })

kp(code="ECON-003", course="ECON1221", knowledge_point="乘数 1/(1 − c1 − b1)",
   subtype="公式未接含义", source="real:ECON1221-Claude自查#7,#19", difficulty="中",
   request="常识化、直观化地解释这个公式，我想对它有一个完整的印象。",
   material=("C = c0 + c1(Y - T), I = b0 + b1*Y - b2*i, with the interest rate i fixed.\n"
             "Equilibrium output: Y = 1/(1 - c1 - b1) * (autonomous spending), where autonomous spending = c0 - c1*T + b0 - b2*i + G.\n"
             "Multiplier = 1/(1 - c1 - b1). Change in output: ΔY = Multiplier * Δ(autonomous spending)."),
   knowledge_errors=["乘数或其条件说错（应为 0 < c1 + b1 < 1 时乘数大于 1）"],
   readers={
     "零基础": dict(learned=["解一元一次方程", "等比数列求和"],
                  not_learned=["边际消费倾向", "自主支出", "均衡产出", "乘数"]),
     "有前置": dict(learned=["消费函数和投资函数", "令 Y 等于需求解出均衡产出的推导", "等比数列求和"],
                  not_learned=["乘数的直观含义"]),
   })

kp(code="ECON-004", course="ECON1221", knowledge_point="公众持有现金时的货币供给",
   subtype="术语未先定义", source="real:ECON1221-Claude自查#24", difficulty="中",
   request="讲一下这道题怎么做。",
   material=("An economy has $2,000 in currency in total, held either by the public or as bank reserves. "
             "Banks hold reserves equal to 10% of deposits. The public holds currency equal to its deposits. "
             "Find public currency, deposits, reserves and the money supply.\n"
             "Relations: M = C + D, B = C + Res, Res = r*D."),
   knowledge_errors=["四个量里有算错的（公众现金和存款都约为 1818.18，准备金约为 181.82，货币供给约为 3636.36）"],
   readers={
     "零基础": dict(learned=["解一元一次方程", "百分数"],
                  not_learned=["货币供给", "基础货币", "准备金", "准备金率", "货币乘数"]),
     "有前置": dict(learned=["准备金和准备金率", "货币乘数 1/R（公众不持有现金时）"],
                  not_learned=["基础货币", "公众持有现金时的货币供给"]),
   })

kp(code="ECON-005", course="ECON1221", knowledge_point="财政扩张后的产出与消费",
   subtype="切换处漏连接", source="real:ECON1221-Claude自查#17", difficulty="低",
   request="讲一下这道题的解法。",
   material=("Consider a closed economy where C = 100 + 0.6(Y - T), I = 150 + 0.2Y - 1000i, G = 200 and T = 100. "
             "The interest rate is fixed at i = 5%, and equilibrium output is Y = 1700. "
             "Government purchases increase to G = 220. Find the new equilibrium output and the new level of consumption."),
   knowledge_errors=["新产出或新消费算错（应为 1800 和 1120）"],
   readers={
     "零基础": dict(learned=["代入求值", "解一元一次方程"],
                  not_learned=["消费函数", "可支配收入", "均衡产出", "乘数"]),
     "有前置": dict(learned=["消费函数和可支配收入", "均衡产出和乘数"],
                  not_learned=[]),
   })

# ---------------- COMP2711 ----------------
kp(code="COMP-001", course="COMP2711", knowledge_point="用容斥数满射",
   subtype="前提未交代", source="real:COMP2711-Claude第五轮自查#6,#7", difficulty="高",
   request="讲一下怎么用容斥数满射，讲到我能做下面这种题。",
   material=("The number of onto (surjective) functions from a set of m elements to a set of n elements is "
             "sum_{k=0}^{n} (-1)^k * C(n,k) * (n-k)^m.\n"
             "Example: In how many ways can 5 different tasks be assigned to 3 different servers so that every server gets at least one task?"),
   knowledge_errors=["例题答案不是 150"],
   readers={
     "零基础": dict(learned=["函数的定义（每个输入恰好对应一个输出）", "组合数 C(n,k)", "乘法原理"],
                  not_learned=["满射", "容斥原理"]),
     "有前置": dict(learned=["函数与满射的定义", "两个和三个集合的容斥公式", "组合数 C(n,k)"],
                  not_learned=["用容斥数满射"]),
   })

kp(code="COMP-002", course="COMP2711", knowledge_point="唯一存在 ∃! 的量词写法",
   subtype="切换处漏连接", source="real:COMP2711-Claude cheatsheet自查#7", difficulty="中",
   request="写一条速查表条目：唯一存在怎么用量词写出来，要能看懂。",
   material=("Common mistake: writing ∃x (P(x) → Q(x)) for \"some P is Q\". Translation patterns: \"some P is Q\" is ∃x (P(x) ∧ Q(x)); \"every P is Q\" is ∀x (P(x) → Q(x)).\n"
             "Uniqueness quantifier: ∃!x C(x) ≡ ∃x ( C(x) ∧ ∀z ( C(z) → z = x ) )."),
   knowledge_errors=["逻辑式写错"],
   readers={
     "零基础": dict(learned=["命题逻辑中 ∧ 和 → 的真值"],
                  not_learned=["量词 ∀ 和 ∃", "唯一存在"]),
     "有前置": dict(learned=["量词 ∀ 和 ∃ 的含义", "“some P is Q”和“every P is Q”的量词写法"],
                  not_learned=["唯一存在"]),
   })

kp(code="COMP-003", course="COMP2711", knowledge_point="对角线法证明 (0,1) 不可数",
   subtype="切换处漏连接", source="real:COMP2711-GPT自查C08", difficulty="高",
   request="讲一下用对角线法证明 (0,1) 里的实数不可数。",
   material=("Theorem: The interval (0,1) is uncountable.\n"
             "Proof (Cantor's diagonal argument): Suppose r1, r2, r3, ... is a list of all real numbers in (0,1). "
             "Write r_n = 0.d_n1 d_n2 d_n3 ... in decimal, choosing the expansion that does not end in infinitely many 9s. "
             "Construct s = 0.s1 s2 s3 ... where s_n = 4 if d_nn ≠ 4, and s_n = 5 if d_nn = 4. "
             "Then s is in (0,1) but differs from every r_n. Contradiction."),
   knowledge_errors=["结论说错，或构造出的 s 不能保证和每个 r_n 都不同"],
   readers={
     "零基础": dict(learned=["小数表示", "反证法"],
                  not_learned=["可数", "一一对应", "对角线法"]),
     "有前置": dict(learned=["可数的定义（能和自然数一一配对）", "反证法"],
                  not_learned=["对角线法"]),
   })

kp(code="COMP-004", course="COMP2711", knowledge_point="量词移动为什么要求论域非空",
   subtype="前提未交代", source="real:COMP2711-GPT自查C04", difficulty="中",
   request="这条等价为什么要求论域非空？我没看懂。",
   material=("Equivalence (A does not contain x): A ∨ ∃x P(x) ≡ ∃x (A ∨ P(x)). This holds when the domain is nonempty.\n"
             "On an empty domain, ∀x P(x) is true and ∃x P(x) is false."),
   knowledge_errors=["空论域上 ∀、∃ 的真值说反"],
   readers={
     "零基础": dict(learned=["∨ 的真值", "∀ 和 ∃ 的含义"],
                  not_learned=["空论域上量词的真值", "量词移动的条件"]),
     "有前置": dict(learned=["∀ 和 ∃ 的含义", "空论域上 ∀ 为真而 ∃ 为假，以及原因"],
                  not_learned=["量词移动的条件"]),
   })

kp(code="COMP-005", course="COMP2711", knowledge_point="期望的线性性",
   subtype="术语未先定义", source="real:COMP2711-Claude cheatsheet自查#1,#6", difficulty="低",
   request="给这条公式写一条速查表条目：先给公式，再说它一般用来做什么，再解释公式里的符号代表什么，中学生也要能看懂。",
   material=("Linearity of expectation: E[aX + bY + c] = a*E[X] + b*E[Y] + c. "
             "In this course X and Y take finitely many values, and then this holds for any such X and Y, whether or not they are independent."),
   knowledge_errors=["说成需要独立才成立"],
   readers={
     "零基础": dict(learned=["概率", "加权平均"],
                  not_learned=["随机变量", "期望"]),
     "有前置": dict(learned=["随机变量", "期望的定义和计算"],
                  not_learned=["期望的线性性"]),
   })

# ---------------- IEDA1280 ----------------
kp(code="IEDA-001", course="IEDA1280", knowledge_point="经济订货量 EOQ",
   subtype="公式未接含义", source="real:IEDA1280-GPT第三轮自查#01,#03", difficulty="中",
   request="把这两个公式讲成中文逻辑：在算什么、为什么这样乘除、结果用在哪一步。",
   material=("EOQ assumptions: single product; known and constant demand rate; instantaneous replenishment; no shortage; no quantity discounts.\n"
             "Annual relevant cost: C(Q) = (D/Q)*S + (Q/2)*H.\n"
             "Economic order quantity: Q* = sqrt(2DS/H)."),
   knowledge_errors=["公式写错"],
   readers={
     "零基础": dict(learned=["平方根", "平均数"],
                  not_learned=["订货成本", "持有成本", "EOQ"]),
     "有前置": dict(learned=["订货成本和持有成本的含义", "D、S、H 各自的含义和单位"],
                  not_learned=["EOQ 公式的来由"]),
   })

kp(code="IEDA-002", course="IEDA1280", knowledge_point="交货期超过订货周期时的再订货点",
   subtype="前提未交代", source="real:IEDA1280-GPT第三轮自查#05", difficulty="高",
   request="讲这道题，两种交货期都要讲。",
   material=("Annual demand D = 500 units, order quantity Q = 25 units, 52 weeks per year. "
             "Find the reorder point (ROP), defined as the on-hand inventory level at which a new order is placed, when the lead time is (a) L = 2 weeks and (b) L = 6 weeks."),
   knowledge_errors=["再订货点算错（应约为 19.23 件和 7.69 件）"],
   readers={
     "零基础": dict(learned=["单位换算", "除法"],
                  not_learned=["交货提前期", "订货周期", "再订货点", "在途订单"]),
     "有前置": dict(learned=["交货提前期和订货周期", "L ≤ T 时 ROP = D × L"],
                  not_learned=["L > T 时的再订货点"]),
   })

kp(code="IEDA-003", course="IEDA1280", knowledge_point="报童模型的临界比率",
   subtype="公式未接含义", source="real:IEDA1280-GPT第三轮自查#07", difficulty="高",
   request="这个临界比率怎么理解？并用这组数据求最优备货量。",
   material=("Rocky pays $0.5 for each paper and sells it for $1.5. Unsold papers are worthless at the end of the day.\n"
             "Daily demand: 87 (0.03), 88 (0.07), 89 (0.2), 90 (0.4), 91 (0.2), 92 (0.07), 93 (0.03).\n"
             "Critical ratio CR = Cu / (Cu + Co). Stock the smallest Q such that F(Q) ≥ CR, where F(Q) = P(demand ≤ Q)."),
   knowledge_errors=["最优备货量不是 90 份"],
   readers={
     "零基础": dict(learned=["概率", "累计概率"],
                  not_learned=["报童模型", "少订损失 Cu", "多订损失 Co", "边际分析"]),
     "有前置": dict(learned=["报童模型是什么", "Cu 和 Co 的定义", "累计概率"],
                  not_learned=["临界比率的来由"]),
   })

kp(code="IEDA-004", course="IEDA1280", knowledge_point="集合覆盖的贪心启发式",
   subtype="切换处漏连接", source="real:IEDA1280-GPT第二轮自查#03,#08", difficulty="中",
   request="讲一下 (b) 和 (c)。",
   material=("Six zones (1)-(6) must each be covered by at least one 5G tower. Candidate tower sites [1]-[6] cover:\n"
             "[1] -> {1,3}; [2] -> {1,2,4}; [3] -> {1,4,5}; [4] -> {2,6}; [5] -> {3,5}; [6] -> {4,5,6}.\n"
             "Annual costs (in $100,000): [1] 14, [2] 19, [3] 24, [4] 16, [5] 25, [6] 21.\n"
             "(b) Solve the set covering model by the greedy heuristic (at each step, choose the site with the lowest cost per newly covered zone), and find the total annual cost in this solution.\n"
             "(c) Someone claims that the solution in (b) is suboptimal. Do you agree? Explain your answer."),
   knowledge_errors=["贪心方案或总成本算错（应选 [2][6][1]，成本 54）"],
   readers={
     "零基础": dict(learned=["除法和比较大小"],
                  not_learned=["集合覆盖", "贪心启发式", "可行解与最优解"]),
     "有前置": dict(learned=["集合覆盖模型", "可行解与最优解"],
                  not_learned=["贪心启发式"]),
   })

kp(code="IEDA-005", course="IEDA1280", knowledge_point="报童模型适用于哪类商品",
   subtype="术语未先定义", source="real:IEDA1280-GPT第三轮自查#06", difficulty="低",
   request="讲一下这道选择题。",
   material=("Which of these products would be most apt to involve the use of a newsboy model?\n"
             "A) gold coins  B) hammers  C) fresh fish  D) calculators  E) frozen corn"),
   knowledge_errors=["答案不是 C"],
   readers={
     "零基础": dict(learned=[],
                  not_learned=["报童模型", "单期备货", "残值"]),
     "有前置": dict(learned=["报童模型的定义"],
                  not_learned=["怎样判断题目里的商品适不适用报童模型"]),
   })

# ---------------- 三档记分用的数据 ----------------
# 第一档 knowledge_errors：知识错误，触发任意一项，这份讲解记 0 分。
# 第二档 QUESTIONS（卡点问题）：对这个读者，要做到请求里的事，讲解里绝对不能缺的内容。
#        每个问题只有“答上 / 没答上”，卡点分 = 答上的个数 ÷ 总个数。
# 第三档 STEPS（推荐步骤）：我们鼓励的讲解步骤。踩中一步记一步，步骤分 = 踩中的步数 ÷ 总步数。
#        步骤只描述“做到了什么”，不规定措辞、顺序和方法；等价的做法都算。
#
# 一个问题算不算卡点，由三问决定，和 Xia 当时有没有问过无关：
#   1. 去掉它，读者还能不能做到请求里要做的事？能，就不是卡点。
#   2. 换一种合理的讲法，它还是不是必须交代的？只是某一次原输出的写法造成的，就不是卡点。
#   3. 答案是不是已经在读者已学清单里？在，就对这个读者不设。
# 没过三问但值得鼓励的内容，放进推荐步骤。
#
# level（证据级别，只是标签，结果按它分开报告）：
#   原话     = Xia 当时卡在这里，原话直接指向它
#   报告定位 = Xia 当时表示没看懂，卡在哪取自模型自查报告
#   推测     = 没有真实失败作证据，按请求和读者设定推出来的
BOTH = ("零基础", "有前置")
ZERO = ("零基础",)
PRE = ("有前置",)

def q(text, level, ref, quote, accept, readers=BOTH, accept_prereq=None):
    return dict(text=text, level=level, ref=ref, quote=quote, accept=accept,
                readers=readers, accept_prereq=accept_prereq)

def st(text, readers=BOTH):
    return dict(text=text, readers=readers)

QUESTIONS = {
 "ECON-001": [
   q("题目只给了需求式和供给的数值，凭什么能把两者列成等式，这个等式在什么条件下才成立？",
     "原话", "ECON1221-Claude自查#13；Xia 审条目时的批注",
     "你完全没有讲 money supply 和上面的 money demand 是如何连接起来的 / 必须说明题目这样的问法才能判断二者相等，二者相等的条件要说清楚",
     "讲解说清了为什么最后的利率就是让两者相等的那个利率：央行把货币供给定死，利率可以变，两者不相等时利率会变动（任何讲法都算，例如买卖债券，或想持有的钱多于现有的钱时利率上升），一直变到相等为止，停下来的利率就是题目问的均衡利率。读者没学过“均衡”，所以只写“均衡时两者相等”而不说明均衡在这里指什么，不算；只写“令两者相等”或直接列式，也不算。"),
 ],
 "ECON-002": [
   q("IS 曲线上的一个点表示什么？",
     "推测", "按请求推出", "",
     "讲解说出曲线上每个点是一组产出和利率：在这个利率下，商品市场正好均衡时的产出。"),
   q("IS 曲线为什么向右下倾斜？",
     "推测", "按请求推出", "",
     "讲解说出原因：利率升高使投资减少，需求减少，均衡产出减少（或等价的因果说明）。只说“斜率为负”或只指着公式里的负号，不算。"),
 ],
 "ECON-003": [
   q("分母 1 − c1 − b1 代表什么？",
     "原话", "ECON1221-Claude自查#7",
     "1-c1-b1就是saving吗？还是说还要减t？",
     "讲解说出它指什么：每多 1 单位产出（收入）里，没有再变成需求的那一部分。用哪种说法都收；只说“这是分母”或只做代数变形，不算。"),
   q("为什么自主支出增加 1，产出增加的不止 1？",
     "推测", "按请求推出", "",
     "讲解说出原因：多出来的产出变成收入，其中一部分又变成新的需求，一轮一轮累加（或等价的说明）。只写出公式或只代数字，不算。"),
 ],
 "ECON-004": [
   q("题目里的 2000 对应关系式里的哪个量，为什么？",
     "原话", "ECON1221-Claude自查#24",
     "基础货币是个什么概念",
     "讲解说出 2000 是公众手里的现金加银行的准备金，也就是 B = C + Res。用不用“基础货币”这个词都行；用了这个词，就必须说明它指什么。"),
 ],
 "ECON-005": [
   q("新的均衡产出是怎么得到的，这一步在求什么？",
     "推测", "按请求推出", "",
     "讲解说出政府购买增加使需求增加，产出要重新调整到等于需求。用乘数，或把 G = 220 代回去重新解均衡，都收。只列算式、不说这一步在求什么，不算。",
     readers=ZERO),
   q("已经解出 Y 是 1800 了，算消费时代进去的为什么不是 1800？",
     "原话", "ECON1221-Claude自查#17",
     "不是解除 Y 是一千八了吗？",
     "讲解说出消费函数里用的是可支配收入 Y − T，所以要先从 1800 里减去税。只写出代入的算式、不说为什么要减，不算。"),
 ],
 "COMP-001": [
   q("指定 k 个输出不用之后，为什么每个输入都还有 n − k 个选择，而不是像阶乘那样一个比一个少？",
     "原话", "COMP2711-Claude第五轮自查#6",
     "那不应该是 N 减 K 的阶乘这种形式吗？为什么每一个？输入依旧有 n 减 k 个选择呢？",
     "讲解说出函数允许多个输入对应同一个输出，所以每个输入各选各的，互不占用。"),
   q("求和公式里的 k 指的是什么，每一项在数什么？",
     "报告定位", "COMP2711-Claude第五轮自查#7",
     "没懂什么意思？没懂什么意思？",
     "讲解说出 k 代表什么（指定不许用的输出有几个），并让读者能把公式里的项和它数的东西对上。用例题逐项对应或直接解释都收。"),
 ],
 "COMP-002": [
   q("式子里的 C(x) 和 ∀z(C(z) → z = x) 各自保证什么？",
     "原话", "COMP2711-Claude cheatsheet自查#7",
     "之前你说存在和箭头违背，那问题是这里如果x也不是c的对象呢？考后面的z=x补吗",
     "讲解说出 C(x) 保证有一个满足 C 的 x，后半保证任何满足 C 的对象都是这个 x。读者由此能知道“x 自己满足 C”是前半保证的，不是靠 z = x。"),
 ],
 "COMP-003": [
   q("这个证明想说明什么，为什么要先假设有一份完整的列表？",
     "原话", "COMP2711-GPT自查C08",
     "我根本就不理解你这个逻辑是什么……你完全没有说出你的逻辑和目的",
     "讲解说出证明的目标（任何一份号称完整的列表都会漏掉某个数），以及先假设有一份完整列表是为了推出矛盾。"),
   q("为什么后面构造出来的那个数，一定不在前面的列表里？",
     "原话", "COMP2711-GPT自查C08",
     "我完全不知道为什么你后面那样的写法能够完全跳脱出你前面这个列表的写法",
     "讲解说出构造出的数和列表里第 n 个数在第 n 位不同，所以和列表里每一个数都不同。其他能保证这一点的构造也收。"),
 ],
 "COMP-004": [
   q("论域为空时，等价式两边的真假为什么不一样？",
     "报告定位", "COMP2711-GPT自查C04",
     "没懂你意思，你是不是省略东西了",
     "讲解说出 A 为真时左边为真，而右边要找到一个 x、空论域里没有任何对象，所以为假。必须说出“找不到对象”这个原因；只报出两边的真假，不算。",
     accept_prereq="讲解说出 A 为真时左边为真、右边为假，并指出右边为假是因为空论域上存在量词为假。这一条读者已经学过，可以直接引用，不必再解释原因。"),
 ],
 "COMP-005": [
   q("这里的 X、Y 和 a、b、c 都是什么？",
     "原话", "COMP2711-Claude cheatsheet自查#6",
     "这里的X、Y、c都是啥",
     "讲解说出 X、Y 是随机变量并说明随机变量是什么，a、b、c 是固定的数。",
     accept_prereq="讲解说出 a、b、c 是固定的数。X、Y 读者已经学过，一句带过即可。"),
   q("E[X]、E[Y] 代表什么，怎么计算？",
     "原话", "COMP2711-Claude cheatsheet自查#6",
     "EX、EY代表什么，怎么计算？",
     "讲解说出 E[X] 是什么，并给出算法（每个取值乘它的概率再相加）。",
     readers=ZERO),
   q("这条公式一般用来做什么？",
     "原话", "COMP2711-Claude cheatsheet自查#1（Xia 当时的请求）",
     "第二描述公式一般用来做什么",
     "讲解说出公式的用途（例如把一个复杂量的期望拆成几个简单量的期望再相加）。"),
 ],
 "IEDA-001": [
   q("公式里的每个字母各指什么？",
     "原话", "IEDA1280-GPT第三轮自查#03",
     "不要举例子，就按照这个公式在描述什么，你直接把那个字母符号给我讲清楚就可以。",
     "D、Q、S、H 都对应到了中文含义。",
     readers=ZERO),
   q("C(Q) 的两项各在算什么？",
     "原话", "IEDA1280-GPT第三轮自查#01",
     "把公式全部变成中文逻辑理解。",
     "讲解说出两项分别是全年的订货费和全年的持有费，以及 D/Q（一年下单几次）和 Q/2（平均库存）各是什么。只把公式念一遍，或只代数字算一遍，不算。"),
   q("Q* 这个式子是怎么来的？",
     "原话", "IEDA1280-GPT第三轮自查#01",
     "把公式全部变成中文逻辑理解。",
     "讲解说出 Q* 是让全年总费用最低的订货量，并说明它怎么从 C(Q) 得到。用两项相等、求导或其他讲清楚的方法都收。只写“由公式可得”，不算。"),
   q("算出的 Q* 用在哪一步？",
     "推测", "按请求推出（请求里写明要讲“结果用在哪一步”）", "",
     "讲解说出 Q* 是每次订多少。再讲到由它得到订货间隔或一年订几次，也可以，但不要求。"),
 ],
 "IEDA-002": [
   q("交货期是 2 周时，再订货点为什么等于这 2 周的用量？",
     "推测", "按请求推出", "",
     "讲解说出下单后要等 2 周才到货，这段时间只能靠手头的库存，所以要留够这 2 周的用量。只写出乘法算式，不算。",
     readers=ZERO),
   q("交货期是 6 周时，为什么手头不用留够 6 周的用量：少掉的那部分是怎么得出来的？",
     "报告定位", "IEDA1280-GPT第三轮自查#05",
     "这点我需要解释。",
     "讲解说清了结果的来历：以前下的订单在等待期间会到货，并交代到货时间（或在途数量）是怎么推出来的。按到货时间倒推，或用 6 周用量减去在途的几批，都收。只报出时间或数字、不说怎么来的，不算。"),
 ],
 "IEDA-003": [
   q("临界比率怎么理解：为什么要拿累计概率和这个比率比？",
     "报告定位", "IEDA1280-GPT第三轮自查#07",
     "这个怎么理解",
     "讲解说出这个比率为什么是“再多备一份还划不划算”的分界，并把它和累计概率 F(Q) 接上。只给出比率怎么算、算完怎么找备货量，不算。"),
 ],
 "IEDA-004": [
   q("贪心每一轮在比较什么，怎么决定选哪个地点？",
     "推测", "按请求推出", "",
     "讲解说出每一轮比较的是“每新增覆盖一个区域要花多少钱”，而且只数还没被覆盖的区域。"),
   q("凭什么说 (b) 的方案不是最优？",
     "推测", "按请求推出", "",
     "讲解给出一个同样覆盖全部区域、成本更低的具体方案，读者能核对它确实全覆盖。"),
 ],
 "IEDA-005": [
   q("报童模型是个什么模型？",
     "原话", "IEDA1280-GPT第三轮自查#06",
     "这是个什么模型？",
     "讲解在让读者判断选项之前或同时，说出报童模型在决定什么、适用于什么情形。",
     readers=ZERO),
   q("为什么选鲜鱼，判断依据是什么？",
     "推测", "按请求推出", "",
     "讲解说出判断依据（例如卖期结束后剩下的货是否大幅贬值、是否只有一次备货机会），并用它说明鲜鱼符合。只报答案，不算。"),
 ],
}

STEPS = {
 "ECON-001": [
   st("说明货币需求指什么（人们想以现金和活期存款形式持有的钱）", ZERO),
   st("说明货币需求为什么随利率升高而减少（例如拿着钱就放弃了利息）", ZERO),
   st("说明货币供给由央行决定，不随利率变", ZERO),
   st("指出题目问的是均衡利率"),
   st("用同一套道理解释货币供给增加后利率为什么下降"),
 ],
 "ECON-002": [
   st("说明 C、I、G、T 各是什么", ZERO),
   st("说明商品市场均衡 Y = C + I + G 是什么意思（产出等于对商品的需求）", ZERO),
   st("给出 IS 的全称 Investment = Saving，并说明商品市场均衡为什么等价于投资等于储蓄（任何拆法都算）"),
   st("区分沿着曲线移动（只是利率变）和整条曲线平移（G、T 等变）"),
   st("交代向右下倾斜的条件（c1 + b1 < 1）"),
 ],
 "ECON-003": [
   st("说明 c1、b1 各是什么", ZERO),
   st("说明自主支出指什么（和产出无关的那部分需求）", ZERO),
   st("说清 1 − c1 − b1 和储蓄是不是一回事、差在哪"),
   st("给出乘数大于 1 的条件（0 < c1 + b1 < 1）"),
   st("交代前提：利率固定"),
 ],
 "ECON-004": [
   st("说明货币供给 M 指公众手里的现金加存款，银行的准备金不算在内"),
   st("说明准备金和准备金率是什么", ZERO),
   st("说明这道题里 C 是现金（不是消费）、D 是存款", ZERO),
   st("把“公众现金等于存款”“准备金是存款的 10%”这两个条件和 2000 接成一个关系"),
   st("说明这里为什么不能直接套 1/r 的乘数（例如公众留在手里的现金不会再被银行贷出）"),
 ],
 "ECON-005": [
   st("说明 Y − T 是可支配收入、C 是消费", ZERO),
   st("说明新产出是怎么求的（用乘数或重新解均衡都算）", PRE),
   st("说明消费增加的部分从哪里来（可支配收入增加，其中一部分用于消费）"),
   st("交代前提：利率固定，税不变"),
 ],
 "COMP-001": [
   st("说明满射是什么（每个输出都至少被一个输入对应到）", ZERO),
   st("说明为什么转成“至少有一个输出没被用到”，再用全部去减"),
   st("说明为什么一项加一项减（多减掉的要加回来）"),
   st("把例题的各项和 k 的取值对上，说出每一项在数什么"),
   st("说明“指定 k 个输出不用”指的是至少这 k 个不用，不是恰好"),
 ],
 "COMP-002": [
   st("说明 ∀ 和 ∃ 的含义", ZERO),
   st("说明 z 是任取的对象（也可以就是 x 本身），z = x 表示它就是 x"),
   st("说明 ∀z 里面的 → 在本式里起什么作用（只对满足 C 的 z 提要求：凡是满足 C 的都等于 x）"),
   st("说明去掉前半的 C(x) 会出什么问题"),
 ],
 "COMP-003": [
   st("说明可数是什么意思（能排成一份带编号的完整列表）", ZERO),
   st("说清列表是怎么排的、每个数怎么写"),
   st("说明选数字时为什么避开 0 和 9，或为什么不用以无限个 9 结尾的写法"),
   st("说明这个论证对任何列表都成立，举的列表只是演示"),
   st("收束：这个数在 (0,1) 里却不在列表里，和“列表完整”矛盾，所以不可数"),
 ],
 "COMP-004": [
   st("说明空论域上 ∀xP(x) 为什么为真（找不到反例）", ZERO),
   st("交代另一个前提：A 里不含 x"),
   st("说明论域非空时两边为什么等价"),
 ],
 "COMP-005": [
   st("说明为什么不需要 X、Y 独立"),
   st("给一个最小的例子，并和公式逐项对上"),
 ],
 "IEDA-001": [
   st("说明平均库存为什么是 Q/2"),
   st("说明两项此消彼长：Q 越大，订货费越少、持有费越多"),
   st("交代适用前提（需求已知且恒定、即时补货、不缺货等，说到主要的即可）"),
 ],
 "IEDA-002": [
   st("说明交货提前期和订货周期各是什么，两者不同", ZERO),
   st("说明再订货点是什么（手头库存降到多少时下单）", ZERO),
   st("先比较交货期和订货周期的长短，再决定怎么算"),
   st("说明这个结果依赖一直在按周期补货，第一次订货时不能照套"),
 ],
 "IEDA-003": [
   st("说明 Cu、Co 各是什么，并给出这道题里的值", ZERO),
   st("说明 F(Q) 是什么（备 Q 份时当天够卖的概率）", ZERO),
   st("说明多备一份什么时候划算（任何讲法都算，例如比较卖得掉多赚的和卖不掉亏掉的）"),
   st("说明为什么取第一个让 F(Q) 达到临界比率的数量"),
   st("交代前提：剩下的报纸不值钱"),
 ],
 "IEDA-004": [
   st("区分可行解（全部覆盖）和最优解（没有更便宜的可行方案）", ZERO),
   st("在某一轮写出“已经覆盖的区域不再算”的具体例子"),
   st("说明有一个更便宜的方案就足以证明 (b) 不是最优，不必证明它是最低"),
   st("指出贪心的哪一步选择把更便宜的方案排除了"),
   st("说明“每一步最划算”为什么不等于“加起来最便宜”（例如先选和后选的塔覆盖重叠，重复花了钱；或贪心只比较当下的比率，不比较整组方案）"),
 ],
 "IEDA-005": [
   st("说明其他选项为什么不符合（可以归在一起讲）"),
   st("说明报童模型里要决定的是备多少货", ZERO),
 ],
}

def build():
    rows = []
    for k in KPS:
        for label, r in k["readers"].items():
            qs = [x for x in QUESTIONS[k["code"]] if label in x["readers"]]
            gate = []
            for i, x in enumerate(qs):
                accept = x["accept_prereq"] if (label == "有前置" and x["accept_prereq"]) else x["accept"]
                gate.append(dict(id=f"q{i+1}", text=x["text"], accept=accept,
                                 source_level=x["level"], source_ref=x["ref"], source_quote=x["quote"]))
            steps = [dict(id=f"s{i+1}", text=x["text"])
                     for i, x in enumerate(y for y in STEPS[k["code"]] if label in y["readers"])]
            assert gate and steps, k["code"] + label
            rows.append(dict(
                id=f'{k["code"]}-{label}', course=k["course"], knowledge_point=k["knowledge_point"],
                subtype=k["subtype"], source=k["source"], difficulty=k["difficulty"],
                reader_known=dict(learned=r["learned"], not_learned=r["not_learned"]),
                request=k["request"], material=k["material"],
                knowledge_errors=k["knowledge_errors"],
                gate_questions=gate,
                recommended_steps=steps,
                split="dev"))
    return rows

if __name__ == "__main__":
    rows = build()
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows))
