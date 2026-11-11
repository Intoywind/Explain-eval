import json, sys

# 长题测试集草稿（2026-11-11，待 Xia 审卡点）。
# 设计依据（Xia 2026-11-11 12:32–12:33）：题目要思维跨度大；请求和材料不能替模型干活；模型的错多出在长输出里。
# 每门课两条：A 是“一份练习”（2–3 道题），B 是“一道综合大题”。每条有零基础 / 有前置两个读者版本，共 12 条。
# 请求只写一句话，不提示该讲什么；材料只放公式和原题，不放解释性的句子。
# 和开发集（drafts/build_items.py、drafts/build_items_long.py）分开：通用 V2 是照开发集的失败写的，测试集不参与归纳。
# RULE：每个卡点对应通用 V2 新增规则 13–18 里的哪一条（"基础" 表示不对应新规则）。只用于跑完后的分析，不发给被测模型和裁判。
# 2026-11-11 13:30 补：每门课再加一条概念理解类长题（T03），见文件后半。产物多一个 *_kind_map.json：每道题是“做题类”还是“概念理解类”。
# 运行：python3 drafts/build_items_long_test.py data/items_long_test.jsonl

BOTH = ("零基础", "有前置")
ZERO = ("零基础",)

def q(text, accept, rule, readers=BOTH):
    return dict(text=text, accept=accept, rule=rule, readers=readers)

def st(text, readers=BOTH):
    return dict(text=text, readers=readers)

ITEMS = []

def item(**k):
    ITEMS.append(k)

# ====================== ECON1221 ======================
item(code="ECON-T01", course="ECON1221", knowledge_point="三个乘数、储蓄悖论、可贷资金与政府赤字（一份练习）",
     source="notes:ECON1221_期中复习_公式与知识点 4.2–4.6（第 3 题数字为新编）",
     request="这份练习帮我讲一遍，讲完我要能自己做这类题。",
     material=(
       "Short-run model (Problems 1 and 2): C = c0 + c1(Y - T). I, G and T are given numbers; the interest rate is fixed. "
       "Equilibrium: Y = C + I + G. Private saving: S = Y - T - C. "
       "Multipliers: ΔY/ΔG = 1/(1 - c1); ΔY/ΔT = -c1/(1 - c1).\n"
       "Long-run model (Problem 3): output is fixed. National saving = private saving + public saving. "
       "The real interest rate r adjusts so that national saving = investment.\n\n"
       "Problem 1. c1 = 0.8. Find the change in equilibrium output when (a) G rises by 100; (b) T is cut by 100; "
       "(c) G and T both rise by 100.\n"
       "Problem 2. c1 = 0.8, T = 100, I = 200, G = 100. Initially c0 = 180. Then households decide to save more and c0 falls to 160. "
       "Find equilibrium output and private saving before and after.\n"
       "Problem 3. Private saving is 300 + 2000r. Investment is 500 - 3000r. "
       "(a) The government budget is balanced. Find r and investment. "
       "(b) The government now runs a deficit of 50. Find the new r and investment. "
       "(c) By how much does investment fall?"),
     knowledge_errors=[
       "（第 1 题）产出变化算错（应为增加 500、增加 400、增加 100）",
       "（第 2 题）产出或储蓄算错（产出应为 2000 和 1900，私人储蓄前后都是 200）",
       "（第 3 题）利率或投资算错（应为 4% 和 380，5% 和 350，投资减少 30）"],
     readers={
       "零基础": dict(learned=["解一元一次方程", "等比数列求和", "需求、供给的一般含义"],
                    not_learned=["边际消费倾向", "可支配收入", "均衡产出", "乘数", "私人储蓄、公共储蓄、国民储蓄",
                                 "可贷资金市场", "实际利率", "挤出"]),
       "有前置": dict(learned=["消费函数 C = c0 + c1(Y − T)", "令 Y = C + I + G 求均衡产出",
                              "政府购买乘数 1/(1 − c1) 的逐轮解释", "私人储蓄、公共储蓄、国民储蓄的定义",
                              "投资随利率上升而减少"],
                    not_learned=["税收乘数", "平衡预算乘数", "储蓄悖论", "可贷资金市场均衡", "挤出"]),
     },
     gates=[
       q("（第 1 题）为什么政府多花 100，产出增加的不止 100？",
         "讲解说出原因：多出来的产出变成收入，其中一部分又被花掉变成新的需求，一轮一轮累加（或等价的说明）。只写出公式或只代数字，不算。",
         "基础", ZERO),
       q("（第 1 题）同样是 100，减税带来的产出增加为什么比政府购买少：税收乘数的分子为什么是 c1 而不是 1？",
         "讲解说出：减税的 100 先到家庭手里，家庭只花掉其中 c1 的部分（本题是 80），其余存起来，所以第一轮变成需求的只有 80；政府购买的 100 在第一轮全部是需求。只写出两个公式或只代数字，不算。",
         "规则15"),
       q("（第 2 题）为什么令 Y = C + I + G 就能求出产出，这一步在求什么？",
         "讲解说出这一步在找“生产出来的东西正好全部有人买”的产出水平（产出等于对商品的总需求），并说明短期里企业按需求决定生产多少。只写“均衡时产出等于需求”而不说明均衡指什么，不算；只列式求解，不算。",
         "规则14", ZERO),
       q("（第 2 题）每家都想多存钱，为什么最后存下来的总额没有变多？",
         "讲解给出因果链：大家少消费，企业卖得少、生产得少，收入下降，收入低了能存的也少，抵掉了想多存的那部分（或等价说明，例如一个人少花的钱就是别人少赚的钱）。只报出前后储蓄都是 200，不算。",
         "规则14"),
       q("（第 3 题）国民储蓄是什么，为什么它是可以借给企业的钱的来源？",
         "讲解说出国民储蓄是家庭存下的钱加上政府收支的结余（赤字时为负），这些没花掉的钱通过金融体系借给要投资的企业。只给定义式不算。",
         "基础", ZERO),
       q("（第 3 题）凭什么令国民储蓄等于投资就能求出利率：两边不相等时利率会怎么变？",
         "讲解说出利率是借钱的价格：想借的钱多于可借的钱时利率被抬高，反过来被压低，一直变到两边相等为止（至少说清一个方向，并说明停在相等处）。只写“均衡时储蓄等于投资”或直接列式，不算。",
         "规则14"),
       q("（第 3 题）政府出现赤字，利率为什么会上升？",
         "讲解说出：赤字意味着公共储蓄为负（政府自己要借钱），可以借给企业的钱变少，在原来的利率下钱不够借，利率被抬高。只说“供给曲线左移”而不说明为什么，不算；只算出 5%，不算。",
         "规则14"),
       q("（第 3 题）政府赤字是 50，为什么投资只减少了 30，另外 20 从哪里来？",
         "讲解说出利率升高后家庭愿意多存钱，私人储蓄从 380 增加到 400，多出的 20 补上了赤字的一部分。只报出投资减少 30，不算。",
         "规则17"),
     ],
     steps=[
       st("（第 1 题）说明 c1 是什么（收入每多 1 元，多消费多少）", ZERO),
       st("（第 1 题）说明税收乘数前的负号是什么意思（加税让产出减少，减税让产出增加）"),
       st("（第 1 题）说明 (c) 里两种变化为什么不会正好抵消（政府的 100 全部成为需求，加税只让家庭少花 80）"),
       st("（第 2 题）说明 c0 下降代表什么（同样的收入下每家都少花一些、想多存一些）", ZERO),
       st("（第 2 题）说明私人储蓄 S = Y − T − C 的含义（收入交完税、花完之后剩下的）", ZERO),
       st("（第 2 题）说明“多存钱总储蓄不变”依赖短期设定：产出由需求决定，利率和投资固定"),
       st("（第 3 题）说明实际利率是什么", ZERO),
       st("（第 3 题）说明投资为什么随利率上升而减少", ZERO),
       st("（第 3 题）给出“挤出”这个名称并说明它指什么"),
       st("说明第 2 题和第 3 题为什么不矛盾：第 2 题是短期（产出随需求变），第 3 题是长期（产出固定，利率调整）"),
     ])

item(code="ECON-T02", course="ECON1221", knowledge_point="IS–LM：财政扩张与挤出（一道综合大题）",
     source="notes:ECON1221_Tutorial公式精讲_常理版 公式 11.x（题目数字为新编）",
     request="讲一下这道题。",
     material=(
       "An economy is described by: C = 200 + 0.5(Y - T), I = 300 - 1000i, G = 150, T = 200. "
       "Real money demand is 0.5Y - 5000i. The real money supply is 250.\n"
       "(a) Derive the IS relation and the LM relation.\n"
       "(b) Find equilibrium output and the equilibrium interest rate.\n"
       "(c) Government purchases rise to 210. Find the new equilibrium output and interest rate.\n"
       "(d) Suppose that in (c) the central bank had instead kept the interest rate at 5%. What would output be?"),
     knowledge_errors=[
       "IS 或 LM 关系推错（IS 应为 Y = 1100 − 2000i 或等价形式，LM 应为 Y = 500 + 10000i 或等价形式）",
       "均衡产出或利率算错（应为 (b) Y = 1000、i = 5%；(c) Y = 1100、i = 6%；(d) Y = 1120）"],
     readers={
       "零基础": dict(learned=["解一元一次方程和二元一次方程组", "一次函数和坐标图"],
                    not_learned=["消费函数", "均衡产出", "乘数", "货币需求", "货币供给", "IS 关系", "LM 关系", "挤出"]),
       "有前置": dict(learned=["消费函数 C = c0 + c1(Y − T)", "令 Y = C + I + G 求均衡产出", "乘数",
                              "货币需求函数的含义（随收入增加、随利率下降）",
                              "给定收入时怎样由货币需求等于货币供给求出利率"],
                    not_learned=["IS 关系", "LM 关系", "两个市场同时均衡", "挤出"]),
     },
     gates=[
       q("推 IS 关系时为什么令 Y = C + I + G，这个等式在说什么？",
         "讲解说出这个等式表示“生产出来的东西正好全部有人买”（产出等于对商品的总需求），并说明短期里企业按需求决定生产多少。只写“商品市场均衡”而不说明均衡指什么，不算；只列式，不算。",
         "规则14", ZERO),
       q("货币需求为什么随收入增加、随利率升高而减少？",
         "讲解对两个方向都给出理由（例如收入高交易多、需要更多钱；利率高时拿着钱放弃的利息多）。只说“需求式就是这样”或只指出正负号，不算。",
         "基础", ZERO),
       q("IS 关系上的一组 (Y, i) 代表什么，LM 关系上的一组 (Y, i) 又代表什么？",
         "讲解对两条都说出含义：IS 上的每组数值让商品市场平衡（生产的正好全部有人买），LM 上的每组数值让货币市场平衡（人们想持有的钱等于央行提供的钱）。只给方程，或只说“IS 是商品市场、LM 是货币市场”而不说一组数值意味着什么，不算。",
         "规则15"),
       q("求均衡时为什么要把两条关系联立，只满足其中一条为什么不行？",
         "讲解说出产出和利率是同一组数，要同时让两个市场都平衡；只满足一条时另一个市场不平衡，产出或利率还会继续变（任何讲法都算）。只说“联立求解”或“交点就是均衡”，不算。",
         "规则13"),
       q("政府购买增加后，利率为什么会从 5% 升到 6%？",
         "讲解给出因果链：政府多买使产出和收入上升，收入高了人们想持有的钱变多，而央行提供的钱没变，利率被抬高（任何讲法都算，例如人们卖债券换钱）。只说“IS 右移、交点往右上移”或只算出 6%，不算。",
         "规则14"),
       q("同样是政府购买增加 60，利率保持 5% 时产出增加 120，为什么 (c) 里只增加 100，少掉的 20 去哪了？",
         "讲解说出：利率升高使投资减少（本题减少 10），投资减少又通过乘数使产出少增加 20；至少要说出“利率上升压低了投资，抵掉了一部分增加”。只报出 1120 和 1100 两个数，或只给“挤出”这个名词，不算。",
         "规则17"),
     ],
     steps=[
       st("说明消费函数里 0.5 的含义（收入每多 1 元，多消费 0.5 元）", ZERO),
       st("说明利率不变时产出变化是政府购买变化的 2 倍，以及 2 是怎么来的", ZERO),
       st("说明 IS 关系里产出为什么随利率升高而下降（利率高，投资少，需求和产出低）"),
       st("说明 LM 关系里利率为什么随产出升高而上升"),
       st("说明政府购买增加改变的是 IS 关系（同一利率下产出更高），LM 关系没有变"),
       st("给出“挤出”这个名称并说明它指什么"),
       st("算出投资从 250 降到 240"),
       st("说明 (d) 里央行要增加货币供给才能把利率保持在 5%"),
       st("把求出的产出和利率代回两条关系核对"),
     ])

# ====================== COMP2711 ======================
item(code="COMP-T01", course="COMP2711", knowledge_point="鸽巢原理设计分组、两枚硬币的 Bayes（一份练习）",
     source="notes:COMP2711_第四轮_计数与组合 R4.4；COMP2711_第五轮_容斥与概率 R5.4（F2025 Midterm Problem 9）",
     request="这两道题帮我讲一遍，讲到我能自己做同类的题。",
     material=(
       "Pigeonhole principle: if k+1 objects are placed into k groups, with each object in exactly one group, "
       "then some group contains at least two objects.\n"
       "Total probability: P(E) = P(E|F)P(F) + P(E|F^c)P(F^c). Bayes' theorem: P(F|E) = P(E|F)P(F) / P(E).\n\n"
       "Problem 1. Consider an 8 x 8 grid of 1 x 1 cells. If 17 cells are colored red, prove that there exist at least two red cells "
       "that share a common corner. (Two cells that touch only diagonally also share a corner.)\n"
       "Problem 2. Two coins look similar to each other. One of them is a fair coin: P(heads) = 1/2. "
       "The other coin is a biased coin: P(heads) = 2/3. We pick one of the coins at random and toss it once, resulting in heads. "
       "Then we pick the other coin and toss it three times, resulting in two heads. "
       "Let D be the event: first coin heads in 1 toss and second coin 2 heads in 3 tosses. "
       "Let B be the event: the first coin is biased. (a) Calculate P(D | B). (b) Calculate P(B | D)."),
     knowledge_errors=[
       "（第 1 题）分组不能保证同组两格共角点，或组数数错（按 2 × 2 分块应为 16 块）",
       "（第 2 题）概率算错（应为 P(D | B) = 1/4，P(B | D) = 9/17）"],
     readers={
       "零基础": dict(learned=["乘法和除法", "证明要对所有情况都成立", "概率的基本含义（0 到 1 之间，表示可能性大小）", "分数运算"],
                    not_learned=["鸽巢原理", "条件概率", "独立", "全概率公式", "Bayes 定理"]),
       "有前置": dict(learned=["鸽巢原理的结论（k+1 个对象放进 k 组，必有一组至少两个）",
                              "条件概率 P(A|B) = P(A∩B)/P(B)", "独立事件的概率可以相乘", "组合数 C(n, k)"],
                    not_learned=["怎样为具体题目设计分组", "全概率公式", "Bayes 定理"]),
     },
     gates=[
       q("（第 1 题）为什么 17 个红格放进 16 个组，就一定有一组里有两个红格？",
         "讲解给出理由：如果每组最多一个红格，总共最多 16 个，放不下 17 个（或等价说明）。只引用原理的名字或原话，不算。",
         "规则13", ZERO),
       q("（第 1 题）为什么要把网格分成 2 × 2 的小块，而不是别的分法？",
         "讲解说出分组必须满足“落在同一组的任意两格一定共角点”，2 × 2 小块的四格都碰到小块中心那个顶点，所以同一块里的两格就是题目要的两格。只说“分成 16 块”或只说组数比红格少，不算。",
         "规则13"),
       q("（第 2 题）P(D | B) 这种带竖线的写法是什么意思？",
         "讲解说出竖线右边是已经知道或假定的条件、左边是要问的事件，并用本题说明 P(D | B) 是“假定第一枚是偏币时，看到这组结果的概率”。只读出符号或只给英文名，不算。",
         "基础", ZERO),
       q("（第 2 题）算 P(D | B) 时，为什么可以把几次抛掷的概率直接乘起来，“三次里两次正面”为什么还要乘 3？",
         "讲解说出两点：确定了哪枚是哪枚之后，各次抛掷互不影响，所以概率相乘；两次正面可以落在三次里的 3 种位置，每种位置的概率相同，所以乘 3。只写出算式，不算；两点缺一点，不算。",
         "规则13", ZERO),
       q("（第 2 题）P(B | D) 和 P(D | B) 问的有什么不同，为什么不能把 (a) 的答案直接当成 (b) 的答案？",
         "讲解说出 (a) 是“假定第一枚是偏币，看到这组结果的可能性”，(b) 是“已经看到这组结果，第一枚是偏币的可能性”，条件和要问的事对调了；并说明要得到 (b) 还得考虑第一枚是均匀币时看到同样结果的可能性。只说“两者不同，要用 Bayes”，不算。",
         "规则13"),
       q("（第 2 题）分母 P(D) 是怎么来的，为什么是两项相加？",
         "讲解说出看到这组结果有两种来源（第一枚是偏币、第一枚是均匀币），两种不会同时发生且合起来是全部可能，所以相加；并说明每一项是“这种来源的概率 × 这种来源下看到这组结果的概率”。只写出算式，不算。",
         "规则17"),
     ],
     steps=[
       st("（第 1 题）说明结论要对任意 17 个红格都成立，不能只验证一种涂法"),
       st("（第 1 题）说明每个格子恰好属于一个小块（不重叠、不遗漏）"),
       st("（第 1 题）说明 17 是最小的保证数：给出 16 个红格两两不共角点的放法"),
       st("（第 2 题）说明 P(B) = 1/2 是怎么来的（随机挑一枚先抛）"),
       st("（第 2 题）说明第一枚是偏币时，第二枚就是均匀币，反过来也一样"),
       st("（第 2 题）算出第一枚是均匀币时看到这组结果的概率 2/9，并写出算法"),
       st("（第 2 题）说明 9/17 略高于 1/2 意味着什么（这组结果稍微偏向“第一枚是偏币”）"),
       st("（第 2 题）给出同类题的做法步骤（找来源、写每个来源下的概率、求总概率、相除）"),
     ])

item(code="COMP-T02", course="COMP2711", knowledge_point="掷骰子的期望与方差、平方的期望与乘积的期望（一道综合大题）",
     source="notes:COMP2711_第六轮_随机变量 R6.3（F2025 Midterm Problem 10）",
     request="讲一下这道题怎么做。",
     material=(
       "(a) Let X1, X2, ..., X100 be the outcomes of 100 independent rolls of a fair die.\n"
       "(i) What are E(X1) and var(X1)?\n"
       "(ii) Define the random variable Y to be X1 - 2*X2 + X3. What are E(Y) and var(Y)?\n"
       "(iii) Define the random variable Z = X1 - X2 + X3 - X4 + ... + X99 - X100. What are E(Z) and var(Z)?\n"
       "(b) Assume two scenarios. Scenario 1: Roll 1 fair die and take the square of the number that comes up. "
       "Scenario 2: Roll 2 fair dice and multiply the outputs. Which expected value is higher? Explain your reason."),
     knowledge_errors=[
       "期望或方差算错（应为 (i) 7/2 和 35/12；(ii) 0 和 35/2；(iii) 0 和 875/3）",
       "(b) 的结论或数值错（应为情景 1 更高：91/6 对 49/4）"],
     readers={
       "零基础": dict(learned=["概率的基本含义", "期望的定义（各取值乘概率再相加）", "分数运算"],
                    not_learned=["期望的线性性", "方差", "独立", "方差的运算规则"]),
       "有前置": dict(learned=["期望及其线性性", "方差的定义 Var(X) = E[(X − μ)²]"],
                    not_learned=["独立", "方差的运算规则", "乘积的期望"]),
     },
     gates=[
       q("方差是什么，它在量什么？",
         "讲解说出方差量的是取值离平均值有多远（离平均的距离平方后按概率平均），越大表示越分散。只给定义式不解释，不算。",
         "基础", ZERO),
       q("方差里系数为什么要平方：−2X2 这一项为什么贡献 4 倍而且是加上去的，(iii) 里一加一减为什么不会把方差抵消成 0？",
         "讲解说出方差看的是离平均值距离的平方：乘 −2 让距离变成 2 倍、平方后是 4 倍，负号平方后没有了；所以减去一个变量同样增加波动，不会抵消。只写“系数要平方”或只报出结果，不算。",
         "规则15"),
       q("为什么可以把各项的方差直接相加，题目里哪个条件保证了这一点？",
         "讲解指出依据是各次掷骰子相互独立，并说明这个条件不满足时不能直接相加（给一句理由或一个例子即可，例如同一个变量加自己）。只说“因为独立”而不提不独立时会怎样，不算。",
         "规则18"),
       q("(b) 里为什么两颗骰子乘积的期望可以写成两个期望相乘，而一颗骰子平方的期望不能这样写？",
         "讲解说出两颗骰子互相独立，所以乘积的期望等于期望的乘积；平方是同一颗骰子的点数和自己相乘，自己和自己不独立，所以 E[a²] 不等于 (E[a])²。只算出 91/6 和 49/4，不算；用 36 种组合直接算出 49/4 但没说明平方为什么不能拆，不算。",
         "规则13"),
     ],
     steps=[
       st("说明两个随机变量独立是什么意思", ZERO),
       st("写出 E(X1²) = 91/6 的算法，并由它得到方差 35/12"),
       st("对比：期望相加不需要独立，方差相加需要"),
       st("说明 (iii) 里有 50 个加号和 50 个减号，期望因此抵消"),
       st("给一个不独立时方差不能直接相加的具体例子"),
       st("说明平方那种情景更高的原因：两者之差正好是方差，方差不会是负的，骰子点数不是固定值所以大于 0（或等价的直观解释）"),
       st("用 36 种组合或其他办法核对乘积的期望"),
     ])

# ====================== IEDA1280 ======================
item(code="IEDA-T01", course="IEDA1280", knowledge_point="加权中位数选址与受限地点、数量折扣下的订货量（一份练习）",
     source="notes:IEDA1280_第2轮_设施选址 R2.3；IEDA1280_第3轮_库存分析 R3.5",
     request="这两道题帮我讲一遍，讲到我能自己做同类的题。",
     material=(
       "Formulas: EOQ: Q* = sqrt(2DS/H). Total annual cost: TC(Q) = (D/Q)*S + (Q/2)*H + p*D.\n\n"
       "Problem 1. Five existing machines are located at P1 = (1,1), P2 = (5,2), P3 = (2,8), P4 = (4,4) and P5 = (8,6). "
       "The numbers of trips per day between a new machine and the existing machines are 5, 6, 2, 4 and 8, respectively. "
       "Trips can only follow the x and y coordinate directions. "
       "(a) Find the location of the new machine that minimizes the total travel per day, and that total. "
       "(b) If the machine cannot be placed in the optimal location, find the best alternative site among (5,6), (4,2) and (8,4).\n"
       "Problem 2. The maintenance department of a large hospital uses about 816 cases of liquid cleanser annually. "
       "Ordering costs are $12, carrying costs are $4 per case a year, and the new price schedule indicates that orders of less than 50 cases "
       "will cost $20 per case, 50 to 79 cases will cost $18 per case, 80 to 99 cases will cost $17 per case, and larger orders will cost $16 per case. "
       "Determine the optimal order quantity and the total cost."),
     knowledge_errors=[
       "（第 1 题）位置或总路程算错（最优位置应为 (5, 4)，每日总路程 105；三个备选点的总路程应为 115、114、132，最好的备选是 (4, 2)）",
       "（第 2 题）最优订货量或总成本算错（应为每次订 100 箱，年总成本约 13353.92）"],
     readers={
       "零基础": dict(learned=["平面坐标", "加法和乘法", "开平方"],
                    not_learned=["只能横着竖着走时的距离（曼哈顿距离）", "加权总距离", "加权中位数",
                                 "订货成本、持有成本", "经济订货量 EOQ", "数量折扣"]),
       "有前置": dict(learned=["曼哈顿距离", "加权总距离的计算",
                              "EOQ 公式 Q* = sqrt(2DS/H) 及其含义（让订货费和持有费之和最低的批量）"],
                    not_learned=["加权中位数法", "数量折扣", "把采购费计入总成本"]),
     },
     gates=[
       q("（第 1 题）只能横着竖着走时，两点之间的路程怎么算？",
         "讲解说出路程是横向差的绝对值加纵向差的绝对值，并给出本题里的一个例子。只给名称（曼哈顿距离、rectilinear distance），不算。",
         "基础", ZERO),
       q("（第 1 题）为什么横坐标和纵坐标可以分开各找各的，而且可以来自不同的机器？",
         "讲解说出只能沿横纵方向走时，总路程等于横向路程之和加纵向路程之和，两部分互不影响，所以可以分开各自取最小。只说“两轴分别排序”，不算。",
         "规则13"),
       q("（第 1 题）最优的横坐标（或纵坐标）为什么是累计次数第一次过半的那个？",
         "讲解用“往旁边挪一步”的比较说明：挪一格，一侧的机器都变近、另一侧都变远，哪一侧的总次数多就值得往哪边挪；到了过半的位置，往两边挪都不划算。用本题数字或一般说明都算。只说“按方法找过半的位置”或只列累计表，不算。",
         "规则16"),
       q("（第 2 题）订货费和持有费各是什么，为什么批量越大一个越少、另一个越多？",
         "讲解说出订货费是每下一次单的固定花费，批量大则一年下单次数少；持有费是存货的花费，批量大则平均存货多。只列符号 S、H 不解释，不算。",
         "基础", ZERO),
       q("（第 2 题）算 EOQ 时没有管买货的钱，这里比较方案时为什么必须把买货的钱加进去？",
         "讲解说出：没有折扣时单价固定，全年买货的钱和每次订多少无关，所以可以不管；有折扣时不同批量对应不同单价，买货的钱随方案变，必须计入。只在公式里写上 pD，不算。",
         "规则18"),
       q("（第 2 题）为什么只需要比较 70、80、100 这三个批量，81 到 99 箱和 100 箱以上的为什么不用算？",
         "讲解说出：订货费加持有费在约 70 箱时最低，批量离 70 越远这两项之和越高；同一个价格档里单价不变，所以每一档只需要取离 70 最近的那个批量（门槛 80 和 100）。只列出三个候选而不说明理由，不算。",
         "规则16"),
     ],
     steps=[
       st("（第 1 题）说明权重是运输次数，不是机器台数（总次数 25，一半是 12.5）"),
       st("（第 1 题）把求出的位置代回，算出每日总路程 105"),
       st("（第 1 题）说明新位置的横坐标和纵坐标可以来自不同的机器，新位置不必和原有机器重合"),
       st("（第 1 题）(b) 把三个备选点的总路程逐个算出来再比较"),
       st("（第 1 题）说明离最优位置最近的备选点不一定最好（(5,6) 更近，总路程 115 却比 (4,2) 的 114 高）"),
       st("（第 2 题）说明全量折扣的含义：达到门槛后，这一单的每一箱都按新价"),
       st("（第 2 题）说明约 70 箱落在 18 元这一档，是能实际拿到这个价格的批量"),
       st("（第 2 题）说明 100 箱的存货费更高，但省下的买货钱更多"),
     ])

item(code="IEDA-T02", course="IEDA1280", knowledge_point="关键路径与赶工：把工期缩短 5 周（一道综合大题）",
     source="notes:IEDA1280_第1轮_决策基础与项目分析 R1.4–R1.6（官方样卷 Part II Q3，节选 (b)(c)）",
     request="讲一下这道题。",
     material=(
       "Assume the network and data given in the following table (the time is in weeks).\n"
       "Activity | Preceding Activity | Normal Time | Crash Time | Crash Cost per week\n"
       "A | - | 7 | 6 | $1,000\n"
       "B | A | 3 | 2 | $1,600\n"
       "C | A | 7 | 6 | $1,200\n"
       "D | B | 5 | 4 | $1,500\n"
       "E | D | 3 | 2 | $1,000\n"
       "F | C, D | 4 | 2 | $1,400\n"
       "G | E, F | 5 | 4 | $3,000\n"
       "(a) What is the project duration and the critical path?\n"
       "(b) If you need to shorten the project duration by 5 weeks, what is the cheapest way to shorten the project? "
       "Please provide the total crashing cost for the shortened project."),
     knowledge_errors=[
       "工期或关键路径错（应为 24 周，A–B–D–F–G）",
       "赶工方案或费用错（应为 A、B、C、D、E 各缩 1 周，F 缩 2 周，G 不缩；额外费用 9,100；工期 19 周）"],
     readers={
       "零基础": dict(learned=["加减法", "看懂“某个活动要等另一个活动做完才能开始”这种先后关系"],
                    not_learned=["路径", "工期", "关键路径", "赶工（crashing）"]),
       "有前置": dict(learned=["网络图和先后关系", "路径和关键路径的定义（用时最长的路径决定工期）", "怎样求工期和关键路径"],
                    not_learned=["赶工（crashing）", "多条路径并列最长时怎么缩短"]),
     },
     gates=[
       q("为什么工期是最长那条路径的用时，而不是所有活动的时间加起来？",
         "讲解说出不同路径上的活动可以同时进行，项目要等每一条路径都做完才算完成，所以由最慢的那条决定。只说“关键路径决定工期”或只列出三条路径的用时，不算。",
         "规则13", ZERO),
       q("表里的 Normal Time、Crash Time、Crash Cost per week 各是什么意思，每个活动最多能缩几周是怎么得出来的？",
         "讲解说出 Normal Time 是不赶工时要用的周数，Crash Time 是加钱后最短能做到的周数（不是能缩短的周数），两者之差是最多能缩的周数，Crash Cost per week 是每缩一周多花的钱。只翻译表头，不算。",
         "基础", ZERO),
       q("赶工时为什么只考虑当前最长路径上的活动，缩别的活动为什么没用？",
         "讲解说出工期由最长的路径决定，缩短不在最长路径上的活动不会让最长路径变短，工期不变，钱白花。只说“缩关键活动”，不算。",
         "规则13"),
       q("有两条或三条路径并列最长时，为什么只缩其中一条上的活动没有用，这时该怎样选？",
         "讲解说出并列最长的路径必须每一条都变短，工期才会变短；所以要么缩它们共有的活动，要么每条路径各缩一个，并比较这些方案的费用选最便宜的；并用本题至少一步说明（例如两条并列时缩共有的 D 而不是继续只缩 F，或三条并列时 E 和 F 一起缩花 2,400，比 G 的 3,000、B 和 C 的 2,800 便宜）。只列出每步缩了什么，不算。",
         "规则16"),
     ],
     steps=[
       st("列出三条路径和各自的用时（23、24、23 周）"),
       st("说明 F 要等 C 和 D 都完成、G 要等 E 和 F 都完成", ZERO),
       st("每缩完一步，重新列出各条路径的长度，再决定下一步"),
       st("说明为什么每缩完一步都要重新看哪些路径最长（原来不是最长的路径可能变成并列最长）"),
       st("说明 A 最便宜但只能缩 1 周，之后要换别的活动"),
       st("说明不能每一步都只挑全表最便宜的活动，要挑能让所有最长路径都变短的最便宜方案"),
       st("给出每个活动最终缩了几周，并核对三条路径都是 19 周"),
       st("说明 9,100 是额外的赶工费用，不是项目的全部开销"),
     ])

# ====================== 概念理解类长题（2026-11-11 13:30 Xia 指出缺这一类后补） ======================
# 做题类长题考“一份练习 / 一道大题讲不讲得清”，概念理解类长题考“一串相连的概念讲不讲得清为什么”。
# 材料只列公式和概念名，按“第 N 部分”编号；卡点、步骤、知识错误都标了属于第几部分。
# 记分（Xia 2026-11-11 定）：做题类讲错一处知识整份清零；概念理解类只清讲错的那一部分。
CONCEPT_CODES = ("ECON-T03", "COMP-T03", "IEDA-T03")

item(code="ECON-T03", course="ECON1221", knowledge_point="物价这条线：名义与实际 GDP、平减指数、CPI 与通胀率、实际利率（概念理解）",
     source="notes:ECON1221_期中复习_公式与知识点 1.4、2.1、2.2、2.6",
     request="这一页帮我讲明白，讲完我要能说清每个指标是干什么的、它们之间是什么关系。",
     material=(
       "Part 1. Nominal GDP_t = Σ p_t q_t. Real GDP_t = Σ p_base q_t. GDP deflator_t = Nominal GDP_t / Real GDP_t × 100.\n"
       "Part 2. CPI_t = (Σ p_t q̄) / (Σ p_base q̄) × 100, where q̄ is a fixed basket. "
       "Inflation rate π_t = (CPI_t − CPI_{t−1}) / CPI_{t−1}.\n"
       "Part 3. CPI vs GDP deflator.\n"
       "Part 4. Real interest rate r ≈ i − π; exactly r = (1 + i)/(1 + π) − 1. Fisher effect. Unexpected inflation."),
     knowledge_errors=[
       "（第 1 部分）把名义 GDP 和实际 GDP 用的价格说反（名义用当年价格，实际用基年价格），或平减指数的式子写错",
       "（第 2 部分）CPI 的式子写错（篮子的数量应固定不变），或通胀率的分母写错（应除以上一年的 CPI）",
       "（第 3 部分）把 CPI 和平减指数的范围说反（进口消费品只进 CPI；本国生产的机器设备和出口品只进平减指数）",
       "（第 4 部分）实际利率的关系写反（应为名义利率减通胀率），或把意外通胀的受益方说反（应为借款人受益、贷款人受损）"],
     readers={
       "零基础": dict(learned=["百分比和增长率的计算", "加权平均", "利息的一般含义"],
                    not_learned=["GDP", "名义 GDP、实际 GDP", "GDP 平减指数", "消费者物价指数 CPI", "通胀率",
                                 "名义利率、实际利率", "费雪效应"]),
       "有前置": dict(learned=["GDP 的定义和支出法", "名义 GDP 和实际 GDP 的定义与计算", "CPI 的定义和固定篮子",
                              "由物价指数算通胀率"],
                    not_learned=["GDP 平减指数", "CPI 与平减指数的区别", "实际利率", "费雪效应", "意外通胀的再分配"]),
     },
     gates=[
       q("（第 1 部分）名义 GDP 变大了，为什么不能说明生产的东西变多了？",
         "讲解说出名义 GDP 是当年价格乘当年数量，数量不变、只是价格上涨也会让它变大。只写出式子不算。",
         "基础", ZERO),
       q("（第 1 部分）实际 GDP 为什么要用基年的价格去乘今年的数量，这样做固定住了什么？",
         "讲解说出把价格固定在基年以后，不同年份之间只剩数量在变，所以实际 GDP 的变化只反映产量的变化。只写出式子或只说“剔除了价格因素”而不说明怎么剔除的，不算。",
         "规则15", ZERO),
       q("（第 1 部分）名义 GDP 除以实际 GDP，为什么得到的是物价水平：分子和分母相同的是什么、不同的是什么？",
         "讲解说出分子和分母用的是同一年的数量，只有价格不同（当年价格对基年价格），所以比值反映当年价格整体上是基年的多少倍；基年等于 100。只写出式子或只说“它衡量物价”不算。",
         "规则15"),
       q("（第 2 部分）CPI 的篮子为什么要固定不变？",
         "讲解说出数量固定以后，两年花费的差别只来自价格的变化（同样一篮子东西，今年要比基年多花多少钱）。只说“篮子是固定的”而不说明固定的作用，不算。",
         "规则18", ZERO),
       q("（第 2 部分）CPI 涨了多少点，为什么不直接就是通胀率，为什么要除以上一年的 CPI？",
         "讲解说出通胀率是价格比上一年涨了百分之几，要用上涨的点数除以上一年的水平；CPI 的点数是相对基年的，不是相对上一年的。只写出式子不算。",
         "规则15", ZERO),
       q("（第 3 部分）CPI 和 GDP 平减指数都在量物价，为什么两个数会不一样？",
         "讲解说出两者算的东西不同：CPI 算消费者买的东西（包括进口消费品，不包括本国造的机器设备和出口品），平减指数算本国生产的东西；并至少举出一种让两者走势不同的情形（例如进口品涨价只推高 CPI）。只说“口径不同”或只列一张对比表而不说明会造成什么差别，不算。",
         "规则13"),
       q("（第 4 部分）名义利率为什么不等于购买力增加的比例；实际利率为什么是名义利率减去通胀率，减掉的那部分代表什么？",
         "讲解说出名义利率是钱数增加的比例，而同一段时间里东西也在变贵；能买到的东西大约按“钱数增加的比例减去价格上涨的比例”增加，减掉的通胀率是钱的购买力被涨价吃掉的部分。只写出式子不算。",
         "规则15"),
       q("（第 4 部分）通胀比事先预期的高，为什么借钱的人得利、放贷的人吃亏？",
         "讲解说出还款的钱数在合同里已经定死，通胀意外升高后这笔钱能买到的东西比双方原先预期的少：贷款人实际收回的购买力变少，借款人实际付出的变少。只报出谁受益谁受损，不算。",
         "基础"),
       q("（第 4 部分）费雪效应：预期通胀上升时，名义利率为什么会跟着上升，是谁的行为造成的？",
         "讲解说出放贷的人预期钱会贬值，要求更高的名义利率才肯借出，借款人预期将来还的钱更不值钱也愿意接受，所以名义利率随预期通胀上升、实际利率大致不变。只写“预期通胀升 1 个点，名义利率升 1 个点”不算。",
         "规则14"),
     ],
     steps=[
       st("（第 1 部分）用两种商品、两个年份的小例子算一遍名义 GDP、实际 GDP 和平减指数"),
       st("（第 1 部分）说明基年的平减指数等于 100"),
       st("（第 1 部分）说明名义 GDP = 物价水平 × 实际 GDP 这层关系"),
       st("（第 2 部分）说明篮子里花钱多的商品权重大，不能把各种商品的涨幅简单平均", ZERO),
       st("（第 3 部分）说明 CPI 的篮子固定、平减指数的“篮子”每年随产出变化"),
       st("（第 3 部分）举一个两者走势不同的具体例子并说明哪个变动更大"),
       st("（第 4 部分）说明近似式在通胀率不高时够用，并交代精确式是怎么来的（一年后的钱数除以一年后的价格）"),
       st("（第 4 部分）区分事先预期到的通胀和意外的通胀"),
       st("说明这几个指标怎么接成一条线：两个物价指数量物价，通胀率由物价指数算出，再用通胀率把名义的量换成实际的量"),
     ])

item(code="COMP-T03", course="COMP2711", knowledge_point="计数的基本公式为什么长这样：乘法与加法原理、排列与组合、两个恒等式、二项式定理、可重复选取（概念理解）",
     source="notes:COMP2711_第四轮_计数与组合 R4.1、R4.3",
     request="这一页帮我讲明白，讲完我要能自己判断一道题该用哪一条，也说得出为什么。",
     material=(
       "Part 1. Product rule: n1 × n2 × ... × nk. Sum rule: |A ∪ B| = |A| + |B| for disjoint A and B.\n"
       "Part 2. Permutations: P(n, r) = n!/(n − r)!. Combinations: C(n, r) = P(n, r)/r! = n!/(r!(n − r)!).\n"
       "Part 3. C(n, r) = C(n, n − r). Pascal's identity: C(n, k) = C(n − 1, k − 1) + C(n − 1, k).\n"
       "Part 4. Binomial theorem: (x + y)^n = Σ_{k=0}^{n} C(n, k) x^(n−k) y^k.\n"
       "Part 5. Ordered selection with repetition: n^r. Unordered selection with repetition: not n^r / r!."),
     knowledge_errors=[
       "（第 1 部分）把分步和分类对应的运算说反（分步用乘，互不重叠的分类用加）",
       "（第 2 部分）排列数或组合数的式子写错，或说“顺序重要时用组合”",
       "（第 3 部分）恒等式写错（应为 C(n, r) = C(n, n − r)；C(n, k) = C(n − 1, k − 1) + C(n − 1, k)）",
       "（第 4 部分）二项式定理的一般项写错（应为 C(n, k) x^(n−k) y^k）",
       "（第 5 部分）说无序且允许重复的选取数等于 n^r / r!"],
     readers={
       "零基础": dict(learned=["集合、元素、子集", "加减乘除和乘方", "多项式相乘怎么展开"],
                    not_learned=["乘法原理、加法原理", "阶乘", "排列、组合", "组合恒等式", "二项式定理", "可重复选取"]),
       "有前置": dict(learned=["乘法原理和加法原理的内容", "阶乘", "排列数、组合数的式子和它们的来历（组合数为什么要除以 r!）",
                              "C(n, r) = C(n, n − r)"],
                    not_learned=["帕斯卡恒等式的理由", "二项式定理", "无序且可重复的选取"]),
     },
     gates=[
       q("（第 1 部分）分步的数目相乘凭什么成立，什么情况下不能直接乘？",
         "讲解说出前提：不管前面怎么选，下一步可选的数目都相同（所以总数是若干个相同的数相加，也就是相乘）；并指出下一步的数目随前面的选择而变（或过程长短不一）时不能直接乘，要先分类。只说“分步就相乘”不算。",
         "规则13"),
       q("（第 1 部分）分类相加要满足什么条件，不满足会出什么错？",
         "讲解说出各类之间不能有重叠（并且合起来要覆盖全部结果）；有重叠时同一个结果会被数两次。只说“分类就相加”不算。",
         "规则18", ZERO),
       q("（第 2 部分）P(n, r) = n!/(n − r)! 里为什么要除以 (n − r)!？",
         "讲解说出依次选 r 个只需要 n × (n − 1) × … 这前 r 个因子，n! 多乘了后面的 n − r 个因子，除以 (n − r)! 正好把它们约掉。只写出式子不算。",
         "规则15", ZERO),
       q("（第 2 部分）组合数为什么是排列数除以 r!：这个 r! 在数什么，凭什么可以统一除掉？",
         "讲解说出同一批 r 个成员在排列里出现了 r! 次（就是这 r 个成员的全部先后顺序），而且每一批重复的次数都一样，所以除以 r! 把它们合成一个结果。只说“组合不讲顺序所以除以 r!”而不说明 r! 是什么、为什么每批都一样，不算。",
         "规则15", ZERO),
       q("（第 2 部分）一道题该用排列还是组合，凭什么判断？",
         "讲解给出判断标准：把选出的对象交换顺序或交换角色以后，结果算不算变了；变了用排列，没变用组合（并各给一个例子，或等价地说清两种情形）。只说“有顺序用排列、没顺序用组合”而不说明怎么看有没有顺序，不算。",
         "规则13"),
       q("（第 3 部分）C(n, r) = C(n, n − r) 为什么成立？",
         "讲解给出理由：选出 r 个留下，等于选出 n − r 个排除，两种选法一一对应；或指出式子里 r! 和 (n − r)! 交换位置后不变。只写出等式不算。",
         "基础", ZERO),
       q("（第 3 部分）帕斯卡恒等式右边的两项各在数什么，为什么加起来正好是左边？",
         "讲解说出固定一个对象，按选没选它分成两类：选了它，再从其余 n − 1 个里选 k − 1 个；没选它，从其余 n − 1 个里选 k 个；两类不重叠，合起来就是全部选法。只用阶乘化简验证，或只用数字验证，不算。",
         "规则15"),
       q("（第 4 部分）二项式定理里 x^(n−k) y^k 这一项的系数为什么是 C(n, k)？",
         "讲解说出 n 个括号每个出一个 x 或一个 y，要得到 x^(n−k) y^k 就是选 k 个括号出 y，有 C(n, k) 种选法，每种选法给出一个相同的项。只写出定理或只用小的 n 展开验证，不算。",
         "规则15"),
       q("（第 5 部分）无序且允许重复的选取，为什么不能用 n^r 除以 r!？",
         "讲解说出除法要求每个结果被重复数了同样多次；允许重复时，不同结果的重复次数不一样（例如两个相同的只有 1 种顺序，两个不同的有 2 种）。只说“不能这样算”不算。",
         "规则18"),
     ],
     steps=[
       st("（第 1 部分）用一个小例子把乘法原理数出的结果全部列出来核对", ZERO),
       st("（第 1 部分）说明同一道题里，类别之间相加、同一类内部的步骤相乘"),
       st("（第 2 部分）说明阶乘是什么，以及为什么规定 0! = 1", ZERO),
       st("（第 2 部分）用小例子（例如 3 个里选 2 个）列出全部排列，展示每一组成员出现了几次", ZERO),
       st("（第 3 部分）用具体数字验证帕斯卡恒等式，或把它对应到杨辉三角里“上一行相邻两数相加”"),
       st("（第 4 部分）用 (x + y)² 或 (x + y)³ 的展开核对系数"),
       st("（第 5 部分）说明 n^r 是怎么来的（每个位置都有 n 种选择）"),
       st("（第 5 部分）指出无序且可重复的选取要换一种数法（按每一类选了几个来数，或给出隔板法的名称）"),
       st("给出判断一道题用哪一条的顺序（先看顺序或角色重不重要，再看能不能重复选）"),
     ])

item(code="IEDA-T03", course="IEDA1280", knowledge_point="PERT：三点估计、路径的均值与方差、按期完成的概率（概念理解）",
     source="notes:IEDA1280_第1轮_决策基础与项目分析 R1.7",
     request="PERT 这一节帮我讲明白，讲完我要能自己做这类题，也说得出每一步为什么这样算。",
     material=(
       "PERT. Each activity has three time estimates: optimistic t_o, most likely t_m, pessimistic t_p.\n"
       "Part 1. Expected time t_e = (t_o + 4 t_m + t_p)/6. Standard deviation σ = (t_p − t_o)/6. Variance σ² = (t_p − t_o)²/36.\n"
       "Part 2. Path mean = Σ t_e. Path variance = Σ σ². Path standard deviation = √(path variance). "
       "Assumption: activity times are independent.\n"
       "Part 3. z = (D − path mean)/(path standard deviation). P(path is finished by D) ≈ Φ(z), from the z-table.\n"
       "Part 4. P(project is finished by D) = product of the probabilities of all paths, when the paths are independent."),
     knowledge_errors=[
       "（第 1 部分）期望时间或标准差的式子写错（应为 (t_o + 4 t_m + t_p)/6 和 (t_p − t_o)/6）",
       "（第 2 部分）说路径的标准差等于各活动标准差相加",
       "（第 3 部分）z 的式子写错，或把 Φ(z) 说成超过期限才完成的概率",
       "（第 4 部分）把各条路径延期的概率相乘当作项目延期的概率（应为 1 减去各路径都按时的概率）"],
     readers={
       "零基础": dict(learned=["网络图、路径", "关键路径法：工期等于最长路径的用时", "加权平均", "开平方"],
                    not_learned=["期望", "方差、标准差", "独立", "正态分布", "z 值和标准正态表", "PERT"]),
       "有前置": dict(learned=["关键路径法", "期望、方差、标准差的含义", "正态分布、z 值的含义和查表",
                              "两个独立事件同时发生的概率相乘"],
                    not_learned=["三点估计", "路径方差怎么汇总", "PERT 里的独立假设", "项目按期完成的概率"]),
     },
     gates=[
       q("（第 1 部分）期望时间在量什么：算出来的 t_e 是不是这一次一定会用的时间？",
         "讲解说出期望时间是这项活动用时的平均水平（多次执行的平均用时），不保证这一次正好用这么久。只代数字算出 t_e 不算。",
         "基础", ZERO),
       q("（第 1 部分）期望时间的式子里，最可能时间为什么乘 4，为什么除以 6？",
         "讲解说出这是加权平均：最可能时间算四份，乐观和悲观时间各算一份，一共六份，所以除以 6。只写出式子不算。",
         "规则15"),
       q("（第 1 部分）标准差和方差在量什么，为什么用悲观时间减乐观时间来估计？",
         "讲解说出它们量的是实际用时离平均用时有多分散（用时有多不确定）；乐观和悲观估计相差越远，说明用时越没把握，课程规定取这段跨度的六分之一作为标准差的估计。只写出式子不算。",
         "规则15", ZERO),
       q("（第 2 部分）一条路径的波动，为什么是把各活动的方差相加再开平方，而不是把标准差直接相加？",
         "讲解说出各活动有的提前有的延后，偏差会互相抵消一部分，不会总朝同一个方向叠加，所以不能把标准差直接相加；相互独立时能相加的是方差，加完再开平方换回原来的单位。只写出式子或只说“规定如此”不算。",
         "规则13"),
       q("（第 2 部分）“各活动用时相互独立”是什么意思，方差相加为什么需要这个假设？",
         "讲解说出独立指一项活动变慢不会改变另一项活动变慢的可能；如果不独立（例如同一个原因同时拖慢几项活动），偏差会朝同一方向叠加，方差直接相加就不对了。只提到“假设独立”而不说明含义和作用，不算。",
         "规则18"),
       q("（第 3 部分）z 在量什么：分子和分母各代表什么？",
         "讲解说出分子是期限比平均用时多留（或少留）了多少时间，除以标准差是把这段余量换算成“相当于几个标准差”；z 越大，按时完成越有把握。只写出式子或只代数字不算。",
         "规则15", ZERO),
       q("（第 3 部分）查表得到的 Φ(z) 表示什么？",
         "讲解说出 Φ(z) 是这条路径在期限当天或之前完成的概率（标准正态曲线在 z 左边的面积）。只说“查表得到概率”而不说明是哪件事的概率，不算。",
         "基础", ZERO),
       q("（第 4 部分）整个项目按期完成的概率，为什么要把各条路径的概率相乘，而不是只看关键路径？",
         "讲解说出项目完成要求所有路径都完成；不是关键路径的路径用时也有波动，同样可能拖过期限；各路径相互独立时，“都按时”的概率是各自概率相乘。只写出相乘的式子不算。",
         "规则13"),
       q("（第 4 部分）路径的概率相乘需要什么条件，什么时候不能直接乘？",
         "讲解说出路径之间要相互独立，这要求各活动独立而且路径之间没有共用的活动；有共用活动时，这项活动变慢会同时拖长两条路径，不能直接相乘。只提到“独立时相乘”而不说明什么时候不独立，不算。",
         "规则18"),
     ],
     steps=[
       st("（第 1 部分）说明三个时间估计各是什么情形下的用时", ZERO),
       st("（第 1 部分）用一组数字算出一项活动的期望时间、标准差和方差"),
       st("（第 1 部分）说明标准差的单位和时间相同，方差的单位是时间的平方", ZERO),
       st("（第 2 部分）说明路径的平均用时为什么是各活动期望时间相加（活动依次进行）"),
       st("（第 2 部分）用数字例子对比“标准差直接相加”和“方差相加再开平方”得到的结果不同"),
       st("（第 3 部分）说明用正态分布是一种近似", ZERO),
       st("（第 3 部分）说明 z 是负数时怎么查表（Φ(−z) = 1 − Φ(z)）"),
       st("（第 4 部分）说明“不能按期完成”的概率是 1 减去按期完成的概率"),
       st("（第 4 部分）说明关键路径是平均用时最长的那条，但较短的路径也可能拖过期限"),
       st("给出做这类题的步骤顺序（每项活动的均值和方差，汇总到路径，算 z，查表，各路径相乘）"),
     ])



def build():
    rows, rule_map = [], {}
    for it in ITEMS:
        for label, r in it["readers"].items():
            gate = []
            for i, x in enumerate(g for g in it["gates"] if label in g["readers"]):
                gate.append(dict(id=f"q{i+1}", text=x["text"], accept=x["accept"],
                                 source_level="推测", source_ref=it["source"], source_quote=""))
                rule_map[f'{it["code"]}-{label}#q{i+1}'] = x["rule"]
            steps = [dict(id=f"s{i+1}", text=x["text"])
                     for i, x in enumerate(s for s in it["steps"] if label in s["readers"])]
            assert gate and steps
            rows.append(dict(
                id=f'{it["code"]}-{label}', course=it["course"], knowledge_point=it["knowledge_point"],
                subtype="长题", source=it["source"], difficulty="高",
                reader_known=dict(learned=r["learned"], not_learned=r["not_learned"]),
                request=it["request"], material=it["material"],
                knowledge_errors=it["knowledge_errors"],
                gate_questions=gate, recommended_steps=steps, split="test"))
    return rows, rule_map


if __name__ == "__main__":
    rows, rule_map = build()
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(sys.argv[1].replace(".jsonl", "_rule_map.json"), "w", encoding="utf-8") as f:
        json.dump(rule_map, f, ensure_ascii=False, indent=1)
    kind_map = {r["id"]: ("概念理解类" if r["id"].rsplit("-", 1)[0] in CONCEPT_CODES else "做题类") for r in rows}
    with open(sys.argv[1].replace(".jsonl", "_kind_map.json"), "w", encoding="utf-8") as f:
        json.dump(kind_map, f, ensure_ascii=False, indent=1)
    for r in rows:
        print(r["id"], len(r["gate_questions"]), len(r["recommended_steps"]))
