import json, sys

# 测试集条目的唯一来源（2026-11-11 起草，待 Xia 审）。
# 和 drafts/build_items.py（开发集 30 条）分开放：通用 V2 是照开发集的失败写的，测试集不能参与归纳。
# 运行：python3 drafts/build_items_test.py data/items_test.jsonl
# 每个知识点：共用字段 + 两种读者设定（零基础 / 有前置）。split 固定为 "test"。
# RULE：每个卡点问题对应通用 V2 新增规则 13–18 里的哪一条（"基础" 表示不对应新规则，是读者必须先懂的概念）。
#       只用于跑完后分析哪条新规则起了作用，不发给被测模型，也不发给裁判。
KPS = []

def kp(**k):
    KPS.append(k)

BOTH = ("零基础", "有前置")
ZERO = ("零基础",)

def q(text, accept, rule, readers=BOTH):
    return dict(text=text, accept=accept, rule=rule, readers=readers)

def st(text, readers=BOTH):
    return dict(text=text, readers=readers)

# ---------------- ECON1221 ----------------
kp(code="ECON-006", course="ECON1221", knowledge_point="政府购买乘数、税收乘数、平衡预算乘数",
   subtype="公式未接含义", source="notes:ECON1221_期中复习_公式与知识点 4.5", difficulty="中",
   request="直观地讲一下这三个乘数，讲完我要能做下面这类题。",
   material=("Consumption: C = c0 + c1(Y - T). Investment and government purchases do not depend on Y; the interest rate is fixed.\n"
             "Government-purchases multiplier: ΔY/ΔG = 1/(1 - c1). Tax multiplier: ΔY/ΔT = -c1/(1 - c1). Balanced-budget multiplier = 1.\n"
             "Example: c1 = 0.8. Find the change in equilibrium output when (a) G rises by 100; (b) T is cut by 100; "
             "(c) G and T both rise by 100."),
   knowledge_errors=["产出变化算错（应为增加 500、增加 400、增加 100）"],
   readers={
     "零基础": dict(learned=["解一元一次方程", "等比数列求和"],
                  not_learned=["边际消费倾向", "可支配收入", "均衡产出", "乘数"]),
     "有前置": dict(learned=["消费函数 C = c0 + c1(Y − T)", "政府购买乘数 1/(1 − c1) 的逐轮解释", "等比数列求和"],
                  not_learned=["税收乘数", "平衡预算乘数"]),
   })

kp(code="ECON-007", course="ECON1221", knowledge_point="储蓄悖论",
   subtype="切换处漏连接", source="notes:ECON1221_期中复习_公式与知识点 4.6", difficulty="中",
   request="讲一下储蓄悖论，讲完我要能做下面这类题，也要知道这个结论什么时候不适用。",
   material=("Paradox of thrift: in the short run, if all households try to save more (autonomous consumption c0 falls), "
             "demand falls, output and income fall, and total saving may not rise.\n"
             "Model: C = c0 + c1(Y - T); I, G and T are fixed and the interest rate is fixed. Equilibrium: Y = C + I + G. "
             "Private saving: S = Y - T - C.\n"
             "Example: c1 = 0.8, T = 100, I = 200, G = 100. Initially c0 = 180. Then households decide to save more and c0 falls to 160. "
             "Find equilibrium output and private saving before and after."),
   knowledge_errors=["产出或储蓄算错（产出应为 2000 和 1900，私人储蓄前后都是 200）"],
   readers={
     "零基础": dict(learned=["解一元一次方程"],
                  not_learned=["消费函数", "均衡产出", "私人储蓄", "储蓄悖论"]),
     "有前置": dict(learned=["消费函数 C = c0 + c1(Y − T)", "令 Y = C + I + G 求均衡产出", "私人储蓄 S = Y − T − C"],
                  not_learned=["储蓄悖论"]),
   })

kp(code="ECON-008", course="ECON1221", knowledge_point="LM 曲线：为什么向右上倾斜",
   subtype="切换处漏连接", source="notes:ECON1221_Tutorial公式精讲_常理版 公式 11.1", difficulty="中",
   request="LM 曲线这一节帮我讲一遍，讲完我要能做下面这类题。",
   material=("Money market equilibrium: real money demand = real money supply, d0*Y - d1*i = Ms/P.\n"
             "Solving for i gives the LM curve: i = -Ms/(d1*P) + (d0/d1)*Y. The LM curve collects all combinations of (Y, i) "
             "at which the money market is in equilibrium. With a fixed money supply it is upward sloping; "
             "an increase in the money supply shifts it down.\n"
             "Example: Real money demand is 0.5Y - 5000i and the central bank fixes the real money supply at 600. "
             "(a) Derive the LM curve. (b) Find the interest rate on the LM curve when Y = 1700 and when Y = 1800."),
   knowledge_errors=["LM 方程或利率算错（应为 i = −0.12 + 0.0001Y，利率 5% 和 6%），或把倾斜方向说反"],
   readers={
     "零基础": dict(learned=["一次函数和坐标图", "解一元一次方程"],
                  not_learned=["货币需求", "货币供给", "货币市场均衡", "LM 曲线"]),
     "有前置": dict(learned=["货币需求函数的含义（随收入增加、随利率下降）", "给定收入时怎样由货币需求等于货币供给求出利率"],
                  not_learned=["LM 曲线"]),
   })

kp(code="ECON-009", course="ECON1221", knowledge_point="可贷资金市场与政府赤字的挤出",
   subtype="切换处漏连接", source="notes:ECON1221_期中复习_公式与知识点 4.2–4.3（例题数字为新编）", difficulty="中",
   request="讲一下可贷资金市场和政府赤字的影响，讲完我要能做下面这类题。",
   material=("Market for loanable funds (long run; output is fixed). Supply of loanable funds = national saving = private saving + public saving. "
             "Demand for loanable funds = investment. The real interest rate r adjusts so that national saving = investment.\n"
             "Example: Private saving is 300 + 2000r. Investment is 500 - 3000r. "
             "(a) The government budget is balanced (public saving = 0). Find the equilibrium r and investment. "
             "(b) The government now runs a deficit of 50 (public saving = -50). Find the new r and investment. "
             "(c) By how much does investment fall? Why is the fall smaller than the deficit?"),
   knowledge_errors=["利率或投资算错（应为 4% 和 380，5% 和 350，投资减少 30）"],
   readers={
     "零基础": dict(learned=["需求、供给的一般含义", "解一元一次方程"],
                  not_learned=["私人储蓄、公共储蓄、国民储蓄", "可贷资金市场", "实际利率", "挤出"]),
     "有前置": dict(learned=["私人储蓄、公共储蓄、国民储蓄的定义", "投资随利率上升而减少"],
                  not_learned=["可贷资金市场均衡", "挤出"]),
   })

# ---------------- COMP2711 ----------------
kp(code="COMP-006", course="COMP2711", knowledge_point="鸽巢原理：怎样设计分组",
   subtype="前提未交代", source="notes:COMP2711_第四轮_计数与组合 R4.4", difficulty="中",
   request="讲一下怎么用鸽巢原理证这种题，讲到我能自己证下面这道。",
   material=("Pigeonhole principle: if k+1 objects are placed into k groups, with each object in exactly one group, "
             "then some group contains at least two objects.\n"
             "Problem: Consider an 8 x 8 grid of 1 x 1 cells. If 17 cells are colored red, prove that there exist at least two red cells "
             "that share a common corner. (Two cells that touch only diagonally also share a corner.)"),
   knowledge_errors=["分组不能保证同组两格共角点，或组数数错（按 2 × 2 分块应为 16 块）"],
   readers={
     "零基础": dict(learned=["乘法和除法", "证明要对所有情况都成立"],
                  not_learned=["鸽巢原理"]),
     "有前置": dict(learned=["鸽巢原理的结论（k+1 个对象放进 k 组，必有一组至少两个）"],
                  not_learned=["怎样为具体题目设计分组"]),
   })

kp(code="COMP-007", course="COMP2711", knowledge_point="全概率与 Bayes：检测阳性后真有病的概率",
   subtype="公式未接含义", source="notes:COMP2711_第五轮_容斥与概率 R5.4", difficulty="中",
   request="讲一下这种题怎么做，讲到我能自己做同类题。",
   material=("Total probability: if F and its complement F^c split the sample space, P(E) = P(E|F)P(F) + P(E|F^c)P(F^c).\n"
             "Bayes' theorem: P(F|E) = P(E|F)P(F) / P(E).\n"
             "Problem: 1% of people have disease D. If a person has the disease, the test is positive (T) with probability 95%. "
             "If a person does not have the disease, the test is positive with probability 10%. "
             "A person tests positive. What is the probability that this person has the disease?"),
   knowledge_errors=["概率算错（应约为 8.76%），或把 95% 当成答案"],
   readers={
     "零基础": dict(learned=["概率的基本含义（0 到 1 之间，表示可能性大小）", "分数和百分比运算"],
                  not_learned=["条件概率", "全概率公式", "Bayes 定理"]),
     "有前置": dict(learned=["条件概率 P(A|B) = P(A∩B)/P(B)", "乘法规则 P(A∩B) = P(A|B)P(B)"],
                  not_learned=["全概率公式", "Bayes 定理"]),
   })

kp(code="COMP-008", course="COMP2711", knowledge_point="独立随机变量线性组合的方差",
   subtype="前提未交代", source="notes:COMP2711_第六轮_随机变量 R6.3", difficulty="中",
   request="讲一下这种题怎么做，讲到我能自己做同类题。",
   material=("For independent random variables X and Y: Var(aX + bY + c) = a^2 Var(X) + b^2 Var(Y).\n"
             "For one roll X of a fair die: E(X) = 7/2 and Var(X) = 35/12.\n"
             "Problem: Let X1, X2, X3 be the outcomes of three independent rolls of a fair die. Define Y = X1 - 2*X2 + X3. "
             "Find E(Y) and Var(Y)."),
   knowledge_errors=["E(Y) 或 Var(Y) 算错（应为 0 和 35/2）"],
   readers={
     "零基础": dict(learned=["概率的基本含义", "期望的定义（各取值乘概率再相加）"],
                  not_learned=["方差", "独立", "方差的运算规则"]),
     "有前置": dict(learned=["期望及其线性性", "方差的定义 Var(X) = E[(X − μ)²]"],
                  not_learned=["独立", "方差的运算规则"]),
   })

# ---------------- IEDA1280 ----------------
kp(code="IEDA-006", course="IEDA1280", knowledge_point="关键路径法：正推、逆推与松弛时间",
   subtype="公式未接含义", source="notes:IEDA1280_第1轮_决策基础与项目分析 R1.5", difficulty="中",
   request="讲一下正推和逆推怎么做，讲到我能自己算出工期、关键路径和每个活动的松弛时间。",
   material=("Activities (time in weeks; immediate predecessors): A (7; none), B (3; A), C (7; A), D (5; B), E (3; D), "
             "F (4; C and D), G (5; E and F).\n"
             "Forward pass: ES = max{EF of immediate predecessors}, EF = ES + t. "
             "Backward pass: LF = min{LS of immediate successors}, LS = LF - t. Slack = LS - ES.\n"
             "Find the project duration, the critical path and the slack of each activity."),
   knowledge_errors=["工期、关键路径或松弛时间算错（工期应为 24 周，关键路径 A–B–D–F–G，C 和 E 的松弛各 1 周，其余为 0）"],
   readers={
     "零基础": dict(learned=["加减法", "看懂“某个活动要等另一个活动做完才能开始”这种先后关系"],
                  not_learned=["最早/最晚开始和完成时间", "关键路径", "松弛时间"]),
     "有前置": dict(learned=["网络图和先后关系", "路径和关键路径的定义（用时最长的路径决定工期）"],
                  not_learned=["正推、逆推", "松弛时间"]),
   })

kp(code="IEDA-007", course="IEDA1280", knowledge_point="加权中位数选址",
   subtype="公式未接含义", source="notes:IEDA1280_第2轮_设施选址 R2.3", difficulty="中",
   request="讲一下加权中位数法，讲到我能自己做下面这类题。",
   material=("Five existing machines are located at P1 = (1,1), P2 = (5,2), P3 = (2,8), P4 = (4,4) and P5 = (8,6). "
             "The numbers of trips per day between a new machine and the existing machines are 5, 6, 2, 4 and 8, respectively. "
             "Trips can only follow the x and y coordinate directions. "
             "Find the location of the new machine that minimizes the total travel, and the total travel per day.\n"
             "Method (weighted median): for each axis, sort the coordinates, accumulate the weights, "
             "and pick the first coordinate at which the cumulative weight reaches at least half of the total weight."),
   knowledge_errors=["位置或总路程算错（应为 (5, 4)，每日总路程 105）"],
   readers={
     "零基础": dict(learned=["平面坐标", "加法和乘法"],
                  not_learned=["只能横着竖着走时的距离（曼哈顿距离）", "加权总距离", "加权中位数"]),
     "有前置": dict(learned=["曼哈顿距离", "加权总距离的计算"],
                  not_learned=["加权中位数法"]),
   })

kp(code="IEDA-008", course="IEDA1280", knowledge_point="数量折扣下的订货量",
   subtype="前提未交代", source="notes:IEDA1280_第3轮_库存分析 R3.5", difficulty="中",
   request="讲一下数量折扣的题怎么做，讲到我能自己做下面这类题。",
   material=("EOQ: Q* = sqrt(2DS/H). Total annual cost including purchase: TC(Q) = (D/Q)*S + (Q/2)*H + p*D. "
             "All-unit discount: once an order reaches a price break, every unit in that order gets the lower price.\n"
             "Problem: The maintenance department of a large hospital uses about 816 cases of liquid cleanser annually. "
             "Ordering costs are $12, carrying costs are $4 per case a year, and the new price schedule indicates that orders of less than 50 cases "
             "will cost $20 per case, 50 to 79 cases will cost $18 per case, 80 to 99 cases will cost $17 per case, and larger orders will cost $16 per case. "
             "Determine the optimal order quantity and the total cost."),
   knowledge_errors=["最优订货量或总成本算错（应为每次订 100 箱，年总成本约 13353.92）"],
   readers={
     "零基础": dict(learned=["开平方", "乘除法"],
                  not_learned=["订货成本、持有成本", "经济订货量 EOQ", "数量折扣"]),
     "有前置": dict(learned=["EOQ 公式 Q* = sqrt(2DS/H) 及其含义（让订货费和持有费之和最低的批量）"],
                  not_learned=["数量折扣", "把采购费计入总成本"]),
   })

QUESTIONS = {
 "ECON-006": [
   q("为什么政府多花 100，产出增加的不止 100？",
     "讲解说出原因：多出来的产出变成收入，其中一部分又被花掉变成新的需求，一轮一轮累加（或等价的说明）。只写出公式或只代数字，不算。",
     "基础", readers=ZERO),
   q("同样是 100，减税带来的产出增加为什么比政府购买少：税收乘数的分子为什么是 c1 而不是 1？",
     "讲解说出：减税的 100 先到家庭手里，家庭只花掉其中 c1 的部分（本题是 80），其余存起来，所以第一轮变成需求的只有 80；政府购买的 100 在第一轮全部是需求。只写出两个公式或只代数字，不算。",
     "规则15"),
 ],
 "ECON-007": [
   q("为什么令 Y = C + I + G 就能求出产出，这一步在求什么？",
     "讲解说出这一步在找“生产出来的东西正好全部有人买”的产出水平（产出等于对商品的总需求），并说明短期里企业按需求决定生产多少。只写“均衡时产出等于需求”而不说明均衡指什么，不算；只列式求解，不算。",
     "规则14", readers=ZERO),
   q("每家都想多存钱，为什么最后存下来的总额没有变多？",
     "讲解给出因果链：大家少消费，企业卖得少、生产得少，收入下降，收入低了能存的也少，抵掉了想多存的那部分（或等价说明，例如一个人少花的钱就是别人少赚的钱）。只报出前后储蓄都是 200，不算。",
     "规则14"),
   q("这个结论在什么情况下不适用？",
     "讲解说出它依赖短期设定里的至少一点：产出由需求决定，或利率和投资固定不变；并说明换一种情形结论不同（例如长期里多储蓄让利率下降、投资增加）。完全没提适用范围，不算。",
     "规则18"),
 ],
 "ECON-008": [
   q("货币需求为什么随收入增加、随利率升高而减少？",
     "讲解对两个方向都给出理由（例如收入高交易多、需要更多钱；利率高时拿着钱放弃的利息多）。只说“需求式就是这样”或只指出正负号，不算。",
     "基础", readers=ZERO),
   q("LM 曲线上的一个点代表什么？",
     "讲解说出每个点是一组收入和利率，在这组数值下人们想持有的货币正好等于央行提供的货币。只说“LM 是一条曲线”或只给方程，不算。",
     "规则15"),
   q("收入从 1700 变成 1800，利率为什么必须从 5% 升到 6%，中间发生了什么？",
     "讲解给出过程：收入高了，人们想持有的钱变多，而央行提供的钱没变，在原来的利率下钱不够；于是利率上升（任何讲法都算，例如人们卖债券换钱），利率升高让人们愿意少持有一些钱，直到又等于供给。只说“Y 越大 i 越大”“斜率为正”或只代数字，不算。",
     "规则14"),
 ],
 "ECON-009": [
   q("国民储蓄是什么，为什么它是可贷资金的供给？",
     "讲解说出国民储蓄是家庭存下的钱加上政府收支的结余（赤字时为负），这些没花掉的钱通过金融体系借给要投资的企业，所以是可以借出去的钱的来源。只给定义式不算。",
     "基础", readers=ZERO),
   q("凭什么令储蓄等于投资就能求出利率：两边不相等时利率会怎么变？",
     "讲解说出利率是借钱的价格：想借的钱多于可借的钱时利率被抬高，反过来被压低，一直变到两边相等为止（至少说清一个方向，并说明停在相等处）。只写“均衡时储蓄等于投资”或直接列式，不算。",
     "规则14"),
   q("政府出现赤字，利率为什么会上升？",
     "讲解说出：赤字意味着公共储蓄为负（政府自己要借钱），可以借给企业的钱变少，在原来的利率下钱不够借，利率被抬高。只说“供给曲线左移”而不说明为什么，不算；只算出 5%，不算。",
     "规则14"),
   q("政府赤字是 50，为什么投资只减少了 30，另外 20 从哪里来？",
     "讲解说出利率升高后家庭愿意多存钱，私人储蓄从 380 增加到 400，多出的 20 补上了赤字的一部分。只报出投资减少 30，不算。",
     "规则17"),
 ],
 "COMP-006": [
   q("为什么 17 个红格放进 16 个组，就一定有一组里有两个红格？",
     "讲解给出理由：如果每组最多一个红格，总共最多 16 个，放不下 17 个（或等价说明）。只引用原理的名字或原话，不算。",
     "规则13", readers=ZERO),
   q("为什么要把网格分成 2 × 2 的小块，而不是别的分法？",
     "讲解说出分组必须满足“落在同一组的任意两格一定共角点”，2 × 2 小块的四格都碰到小块中心那个顶点，所以同一块里的两格就是题目要的两格。只说“分成 16 块”或只说组数比红格少，不算。",
     "规则13"),
 ],
 "COMP-007": [
   q("P(T|D) 这种带竖线的写法是什么意思？",
     "讲解说出竖线右边是已经知道的条件、左边是要问的事件，并用本题说明 P(T|D) 是有病的人里检测阳性的比例。只读出符号或只给英文名，不算。",
     "基础", readers=ZERO),
   q("检测对病人有 95% 的准确率，为什么阳性的人真有病的概率不是 95%？",
     "讲解说出 95% 是“有病的人里阳性的比例”，题目问的是“阳性的人里有病的比例”，两者看的是不同的人群；并说明健康人数量多，他们的误报占了阳性者的大部分（用人数或概率说明都算）。只说“两个概率不一样”，不算。",
     "规则13"),
   q("分母 P(T) 是怎么来的，为什么要把两部分加起来？",
     "讲解说出阳性的人有两类来源（有病且阳性、没病且阳性），两类不重叠且合起来就是全部阳性的人，所以相加；并说明每一类是“这类人占的比例 × 这类人里阳性的比例”。只写出 0.95 × 0.01 + 0.10 × 0.99，不算。",
     "规则17"),
 ],
 "COMP-008": [
   q("方差是什么，它在量什么？",
     "讲解说出方差量的是取值离平均值有多远（离平均的距离平方后按概率平均），越大表示越分散。只给定义式不解释，不算。",
     "基础", readers=ZERO),
   q("−2X2 这一项，在方差里为什么是乘 4，而且是加上去而不是减掉？",
     "讲解说出方差看的是离平均值距离的平方：乘 −2 让每段距离变成 2 倍，平方后是 4 倍，负号平方后没有了；所以减去一个变量同样增加波动，不会抵消。只写“系数要平方”，不算。",
     "规则15"),
   q("为什么可以把三项的方差直接相加，题目里哪个条件保证了这一点？",
     "讲解指出依据是三次掷骰子相互独立，并说明这个条件不满足时不能直接相加（给一句理由或一个例子即可，例如同一个变量加自己）。只说“因为独立”而不提不独立时会怎样，不算。",
     "规则18"),
 ],
 "IEDA-006": [
   q("最早开始、最早完成、最晚开始、最晚完成各指什么？",
     "讲解对四个量分别说出含义（例如最晚完成是不拖延整个项目的前提下最晚必须做完的时间）。只列缩写和英文全称，不算。",
     "基础", readers=ZERO),
   q("正推时，一个活动有多个前置活动，为什么取它们完成时间里最大的那个？",
     "讲解说出这个活动要等所有前置都做完才能开始，所以由最晚做完的那个决定（用 F 要等 C 和 D 的例子或一般说明都算）。只写公式里的 max 或只报数字，不算。",
     "规则13"),
   q("逆推时，一个活动有多个后继活动，为什么取它们最晚开始时间里最小的那个？",
     "讲解说出这个活动必须赶在所有后继最晚开工之前完成，最早必须开工的那个后继卡得最紧（用 D 要同时赶上 E 和 F 的例子或一般说明都算）。只写公式里的 min 或只报数字，不算。",
     "规则13"),
   q("松弛时间是什么意思，为什么 C 可以晚 1 周而 D 一周都不能晚？",
     "讲解说出松弛是一个活动最多可以推迟多久而不拖延整个项目，并用后继活动的开工时间说明：C 晚 1 周仍赶得上 F，D 只要一晚后面就得跟着推迟。只报出松弛的数字，不算。",
     "规则15"),
 ],
 "IEDA-007": [
   q("只能横着竖着走时，两点之间的路程怎么算？",
     "讲解说出路程是横向差的绝对值加纵向差的绝对值，并给出本题里的一个例子。只给名称（曼哈顿距离、rectilinear distance），不算。",
     "基础", readers=ZERO),
   q("为什么横坐标和纵坐标可以分开各找各的，而且可以来自不同的机器？",
     "讲解说出只能沿横纵方向走时，总路程等于横向路程之和加纵向路程之和，两部分互不影响，所以可以分开各自取最小。只说“两轴分别排序”，不算。",
     "规则13"),
   q("为什么累计权重第一次过半的那个坐标就是最好的位置？",
     "讲解用“往旁边挪一步”的比较说明：挪一格，一侧的机器都变近、另一侧都变远，哪一侧的总次数多就值得往哪边挪；到了过半的位置，往两边挪都不划算。用本题数字（例如从 4 挪到 5 省 14 增 11）或一般说明都算。只说“按方法找过半的位置”，不算。",
     "规则16"),
 ],
 "IEDA-008": [
   q("订货费和持有费各是什么，为什么批量越大一个越少、另一个越多？",
     "讲解说出订货费是每下一次单的固定花费，批量大则一年下单次数少；持有费是存货的花费，批量大则平均存货多。只列符号 S、H 不解释，不算。",
     "基础", readers=ZERO),
   q("算 EOQ 时没有管买货的钱，这里比较方案时为什么必须把采购费 pD 加进去？",
     "讲解说出：没有折扣时单价固定，全年买货的钱和每次订多少无关，所以可以不管；有折扣时不同批量对应不同单价，买货的钱随方案变，必须计入。只在公式里写上 pD，不算。",
     "规则18"),
   q("为什么只需要比较 70、80、100 这三个批量，81 到 99 箱和 100 箱以上的为什么不用算？",
     "讲解说出：订货费加持有费在约 70 箱时最低，批量离 70 越远这两项之和越高；同一个价格档里单价不变，所以每一档只需要取离 70 最近的那个批量（门槛 80 和 100）。只列出三个候选而不说明理由，不算。",
     "规则16"),
 ],
}

STEPS = {
 "ECON-006": [
   st("说明 c1 是什么（收入每多 1 元，多消费多少）", ZERO),
   st("说明税收乘数前的负号是什么意思（加税让产出减少，减税让产出增加）"),
   st("说明 (c) 里两种变化为什么不会正好抵消（政府的 100 全部成为需求，加税只让家庭少花 80）"),
   st("交代前提：利率固定，投资不随产出变化"),
 ],
 "ECON-007": [
   st("说明 c0 下降代表什么（同样的收入下每家都少花一些、想多存一些）", ZERO),
   st("说明私人储蓄 S = Y − T − C 的含义（收入交完税、花完之后剩下的）", ZERO),
   st("说明储蓄为什么恰好不变：均衡时私人储蓄等于 I + G − T，这几个量在题目里固定"),
   st("指出“对一个人成立，对所有人一起做就不成立”这一点"),
 ],
 "ECON-008": [
   st("说明 LM 这个名字的由来（Liquidity preference = Money supply）"),
   st("区分沿着曲线移动（收入变）和曲线本身移动（货币供给变）"),
   st("说明货币供给增加时曲线为什么下移"),
   st("说明“向右上倾斜”依赖央行固定货币供给；央行盯住利率时情况不同"),
 ],
 "ECON-009": [
   st("说明实际利率是什么", ZERO),
   st("说明投资为什么随利率上升而减少", ZERO),
   st("给出“挤出”这个名称并说明它指什么"),
   st("说明这是长期模型（产出固定），和短期里“多储蓄不一定增加储蓄”的结论不同"),
 ],
 "COMP-006": [
   st("说明题目里的“17 个格子涂红”要对任意 17 个格子都成立，不能只验证一种涂法"),
   st("说明每个格子恰好属于一个小块（不重叠、不遗漏）"),
   st("说明 17 是最小的保证数：给出 16 个红格两两不共角点的放法"),
   st("说明如果题目改成“共边”，这个分组就不够用了"),
 ],
 "COMP-007": [
   st("用具体人数（例如一万人）把计算核对一遍"),
   st("说明先验、似然、后验各指本题里的哪个量"),
   st("给出同类题的做法步骤（找来源、写每个来源下的概率、求总概率、相除）"),
   st("说明各个来源必须互不重叠且合起来覆盖所有情况"),
 ],
 "COMP-008": [
   st("说明两个随机变量独立是什么意思", ZERO),
   st("对比：期望相加不需要独立，方差相加需要"),
   st("说明加上常数不改变方差"),
   st("给一个不独立时方差不能直接相加的具体例子"),
 ],
 "IEDA-006": [
   st("说明逆推从哪里开始：终点活动的最晚完成时间设为正推算出的工期"),
   st("说明关键路径上的活动松弛为零，并且要沿箭头连成一条路径"),
   st("列出各条路径的用时，核对工期"),
   st("交代前提：允许并行的活动可以同时进行（人手和资源够）"),
 ],
 "IEDA-007": [
   st("说明权重是运输次数，不是机器台数（总权重的一半是 12.5 次）"),
   st("把求出的位置代回，算出每日总路程"),
   st("说明新位置不必和原有机器重合"),
   st("说明累计权重恰好等于一半时，这个坐标到下一个坐标之间的位置都同样好"),
 ],
 "IEDA-008": [
   st("说明全量折扣的含义：达到门槛后，这一单的每一箱都按新价"),
   st("说明约 70 箱落在 18 元这一档，是能实际拿到这个价格的批量"),
   st("说明 100 箱的存货费更高，但省下的买货钱更多"),
   st("说明本题各档持有费相同所以共用一个 EOQ；持有费按单价比例计时要每档重算"),
 ],
}

def build():
    rows, rule_map = [], {}
    for k in KPS:
        for label, r in k["readers"].items():
            qs = [x for x in QUESTIONS[k["code"]] if label in x["readers"]]
            gate = []
            for i, x in enumerate(qs):
                gate.append(dict(id=f"q{i+1}", text=x["text"], accept=x["accept"],
                                 source_level="推测", source_ref=k["source"], source_quote=""))
                rule_map[f'{k["code"]}-{label}#q{i+1}'] = x["rule"]
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
                split="test"))
    return rows, rule_map

if __name__ == "__main__":
    rows, rule_map = build()
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(sys.argv[1].replace(".jsonl", "_rule_map.json"), "w", encoding="utf-8") as f:
        json.dump(rule_map, f, ensure_ascii=False, indent=1)
    print(len(rows))
