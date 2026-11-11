# 三组正式评分汇总（prompts/judge_v2.md）

- 裁判：gpt-6.1-terra（gpt-6.1-terra），prompt `prompts/judge_v2.md`（sha256 5e5764690400…）；条目文件 `data/items.jsonl`
- 生成时间：2026-11-11T13:29:38+00:00
- 组 = Skill 组 × 被测模型。知识不通过的回答卡点分、步骤分按 0 计；待复核、失败的不计分，单独列出。
- 均值给两种：按回答平均；按条目平均（条目内先平均，再在条目间平均）。两者只在有回答不计分时才可能不同。
- 每个数字后的 [Qn] 指向文末附录的 SQL。

## 1. 份数 [Q1]

| 组 | 当前回答 | ok | 待复核 | 失败 | 未评 |
|---|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | 90 | 90 | 0 | 0 | 0 |
| original_eval × gpt-6.1-sol | 90 | 90 | 0 | 0 | 0 |
| general_v1 × gpt-6-luna | 90 | 90 | 0 | 0 | 0 |
| original_eval × gpt-6-luna | 90 | 90 | 0 | 0 | 0 |

## 2. 主要结果 [Q2] [Q3]

| 组 | ok 份数 | 知识通过率 | 没答全比例 | 卡点分均值（按回答） | 卡点分均值（按条目） | 步骤分均值（按回答） | 步骤分均值（按条目） | 卡点全答上比例 |
|---|---|---|---|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | 90 | 97.8%（不通过 2 份） | 0.0%（0 份） | 0.936 | 0.936 | 0.811 | 0.811 | 91.1% |
| original_eval × gpt-6.1-sol | 90 | 100.0%（不通过 0 份） | 0.0%（0 份） | 0.957 | 0.957 | 0.854 | 0.854 | 91.1% |
| general_v1 × gpt-6-luna | 90 | 96.7%（不通过 3 份） | 0.0%（0 份） | 0.824 | 0.824 | 0.762 | 0.762 | 72.2% |
| original_eval × gpt-6-luna | 90 | 95.6%（不通过 4 份） | 1.1%（1 份） | 0.800 | 0.800 | 0.746 | 0.746 | 72.2% |

卡点全答上 = 知识通过且所有卡点问题都答上。

## 2b. 两份 Skill × 两档模型 [Q2]

每格：卡点分均值 / 步骤分均值 / 卡点全答上比例（按回答平均，只算 ok；所有回答都 ok 时与按条目平均相同）。

| Skill \ 模型 | gpt-6.1-sol | gpt-6-luna |
|---|---|---|
| general_v1 | 0.936 / 0.811 / 91.1% | 0.824 / 0.762 / 72.2% |
| original_eval | 0.957 / 0.854 / 91.1% | 0.800 / 0.746 / 72.2% |

## 2c. 同一模型下两份 Skill 的逐条目比较（original_eval 相对 general_v1）[Q4]

每条条目先在条目内对 3 次重复取平均，再比较 original_eval 和 general_v1；两边都有结果的条目才计入。

| 模型 | 指标 | 条目数 | original_eval 更高 | 持平 | original_eval 更低 | 平均差 |
|---|---|---|---|---|---|---|
| gpt-6.1-sol | 卡点分 | 30 | 3 | 25 | 2 | +0.021 |
| gpt-6.1-sol | 步骤分（附） | 30 | 7 | 21 | 2 | +0.042 |
| gpt-6-luna | 卡点分 | 30 | 6 | 19 | 5 | -0.024 |
| gpt-6-luna | 步骤分（附） | 30 | 2 | 23 | 5 | -0.016 |

## 3. 分布

**卡点分**（份数；括号里是其中知识不通过、按 0 计的份数）[Q5]

| 组 | 0 | 0.5 | 0.667 | 0.75 | 1 |
|---|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | 4（2） | 3 | 0 | 1 | 82 |
| original_eval × gpt-6.1-sol | 1 | 4 | 1 | 2 | 82 |
| general_v1 × gpt-6-luna | 8（3） | 14 | 1 | 2 | 65 |
| original_eval × gpt-6-luna | 13（4） | 7 | 3 | 2 | 65 |

**步骤分**（份数；括号里是其中知识不通过、按 0 计的份数）[Q6]

| 组 | 0 | (0, 0.5) | [0.5, 0.8) | [0.8, 1) | 1 |
|---|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | 8（2） | 0 | 21 | 10 | 51 |
| original_eval × gpt-6.1-sol | 6 | 0 | 17 | 10 | 57 |
| general_v1 × gpt-6-luna | 9（3） | 0 | 25 | 16 | 40 |
| original_eval × gpt-6-luna | 10（4） | 1 | 28 | 10 | 41 |

## 4. 逐条目三组对比 [Q7]

每格：知识通过份数/ok 份数 · 卡点分 · 步骤分（条目内几次重复的平均）。“没答全”列出该组 incomplete 的份数。组名缩写：通用·sol = general_v1 × gpt-6.1-sol，原版·sol = original_eval × gpt-6.1-sol，通用·luna = general_v1 × gpt-6-luna，原版·luna = original_eval × gpt-6-luna。

| 条目 | 通用·sol | 原版·sol | 通用·luna | 原版·luna | 没答全（通用·sol/原版·sol/通用·luna/原版·luna） |
|---|---|---|---|---|---|
| COMP-001-有前置 | 3/3 · 0.83 · 1.00 | 3/3 · 0.83 · 1.00 | 3/3 · 0.50 · 0.92 | 3/3 · 0.50 · 0.92 | 0/0/0/0 |
| COMP-001-零基础 | 3/3 · 0.83 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 0.50 · 0.87 | 3/3 · 0.67 · 1.00 | 0/0/0/0 |
| COMP-002-有前置 | 3/3 · 1.00 · 0.67 | 3/3 · 1.00 · 0.89 | 3/3 · 1.00 · 0.67 | 3/3 · 1.00 · 0.56 | 0/0/0/0 |
| COMP-002-零基础 | 3/3 · 1.00 · 0.83 | 3/3 · 1.00 · 0.75 | 3/3 · 1.00 · 0.75 | 3/3 · 1.00 · 0.75 | 0/0/0/0 |
| COMP-003-有前置 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 0/0/0/0 |
| COMP-003-零基础 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 0/0/0/0 |
| COMP-004-有前置 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 0/0/0/0 |
| COMP-004-零基础 | 3/3 · 1.00 · 0.67 | 3/3 · 1.00 · 0.67 | 3/3 · 1.00 · 0.67 | 3/3 · 1.00 · 0.67 | 0/0/0/0 |
| COMP-005-有前置 | 3/3 · 1.00 · 0.00 | 3/3 · 1.00 · 0.00 | 3/3 · 1.00 · 0.00 | 3/3 · 1.00 · 0.00 | 0/0/0/0 |
| COMP-005-零基础 | 3/3 · 1.00 · 0.00 | 3/3 · 1.00 · 0.00 | 3/3 · 1.00 · 0.00 | 3/3 · 1.00 · 0.00 | 0/0/0/0 |
| ECON-001-有前置 | 3/3 · 0.67 · 1.00 | 3/3 · 0.67 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 0.67 · 1.00 | 0/0/0/0 |
| ECON-001-零基础 | 3/3 · 0.67 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 0.67 · 0.80 | 3/3 · 1.00 · 0.93 | 0/0/0/0 |
| ECON-002-有前置 | 3/3 · 1.00 · 0.89 | 3/3 · 1.00 · 0.67 | 3/3 · 0.83 · 0.67 | 3/3 · 1.00 · 0.67 | 0/0/0/0 |
| ECON-002-零基础 | 3/3 · 1.00 · 0.80 | 3/3 · 1.00 · 0.80 | 3/3 · 1.00 · 0.80 | 3/3 · 1.00 · 0.80 | 0/0/0/0 |
| ECON-003-有前置 | 3/3 · 1.00 · 0.67 | 3/3 · 1.00 · 0.89 | 3/3 · 0.50 · 0.67 | 3/3 · 0.83 · 0.67 | 0/0/0/0 |
| ECON-003-零基础 | 2/3 · 0.50 · 0.53 | 3/3 · 0.50 · 0.80 | 3/3 · 0.50 · 0.80 | 3/3 · 0.83 · 0.73 | 0/0/0/0 |
| ECON-004-有前置 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 0/0/0/0 |
| ECON-004-零基础 | 3/3 · 1.00 · 0.80 | 3/3 · 1.00 · 0.80 | 3/3 · 1.00 · 0.80 | 3/3 · 1.00 · 0.73 | 0/0/0/0 |
| ECON-005-有前置 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 0.00 · 0.67 | 0/0/0/0 |
| ECON-005-零基础 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 0.83 · 1.00 | 3/3 · 1.00 · 1.00 | 0/0/0/0 |
| IEDA-001-有前置 | 3/3 · 1.00 · 1.00 | 3/3 · 0.89 · 1.00 | 3/3 · 0.89 · 1.00 | 3/3 · 0.67 · 1.00 | 0/0/0/0 |
| IEDA-001-零基础 | 3/3 · 0.92 · 1.00 | 3/3 · 0.83 · 1.00 | 3/3 · 0.83 · 1.00 | 3/3 · 0.83 · 1.00 | 0/0/0/0 |
| IEDA-002-有前置 | 3/3 · 1.00 · 0.50 | 3/3 · 1.00 · 0.83 | 3/3 · 0.33 · 0.50 | 2/3 · 0.33 · 0.33 | 0/0/0/1 |
| IEDA-002-零基础 | 2/3 · 0.67 · 0.50 | 3/3 · 1.00 · 0.75 | 0/3 · 0.00 · 0.00 | 0/3 · 0.00 · 0.00 | 0/0/0/0 |
| IEDA-003-有前置 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 0.67 · 1.00 | 0/0/0/0 |
| IEDA-003-零基础 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 0.33 · 0.87 | 3/3 · 0.00 · 0.87 | 0/0/0/0 |
| IEDA-004-有前置 | 3/3 · 1.00 · 0.75 | 3/3 · 1.00 · 0.83 | 3/3 · 1.00 · 0.50 | 3/3 · 1.00 · 0.50 | 0/0/0/0 |
| IEDA-004-零基础 | 3/3 · 1.00 · 0.73 | 3/3 · 1.00 · 0.93 | 3/3 · 1.00 · 0.60 | 3/3 · 1.00 · 0.60 | 0/0/0/0 |
| IEDA-005-有前置 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 0/0/0/0 |
| IEDA-005-零基础 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 3/3 · 1.00 · 1.00 | 0/0/0/0 |

## 5. 知识不通过的回答（9 份）[Q8]

| 组 | 条目 | call | 第几次 | which | 引句 |
|---|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | ECON-003-零基础 | 15 | 3 | 乘数公式写错，或把公式成立的条件说反（公式在 c1 + b1 < 1 时成立；写成 0 ≤ c1 + b1 < 1 或 0 < c1 + b1 < 1 都不算错，说成 c1 + b1 大于或等于 1 时也成立才算错） | 只要 \(1-c_1-b_1\ne0\)，就能解得： / \boxed{Y=\frac{1}{1-c_1-b_1}A} |
| original_eval × gpt-6-luna | IEDA-002-有前置 | 344 | 2 | 再订货点算错（应约为 19.23 件和 7.69 件） | 所以 ROP 约为 **57.69 件**；按整件向上取整时为 **58 件**。 |
| general_v1 × gpt-6-luna | IEDA-002-零基础 | 250 | 1 | 再订货点算错（应约为 19.23 件和 7.69 件） | 六周内预计会用掉约 57.69 units。因此，**理论上的再订货点约为 57.69 units**；按整数单位向上取整，设为 **58 units**。 |
| general_v1 × gpt-6-luna | IEDA-002-零基础 | 251 | 2 | 再订货点算错（应约为 19.23 件和 7.69 件） | 所以交货期为 6 周时，再订货点约为 **57.69 件**。 |
| general_v1 × gpt-6-luna | IEDA-002-零基础 | 252 | 3 | 再订货点算错（应约为 19.23 件和 7.69 件） | - \(L=6\) 周：ROP \(\approx 57.69\) 件，整数库存通常取 **58 件**。 |
| general_v1 × gpt-6.1-sol | IEDA-002-零基础 | 68 | 2 | 再订货点算错（应约为 19.23 件和 7.69 件） | **若按常规公式作答，写 (a) \(19.23\) 件，(b) \(57.69\) 件。** |
| original_eval × gpt-6-luna | IEDA-002-零基础 | 340 | 1 | 再订货点算错（应约为 19.23 件和 7.69 件） | 因此 **ROP = 57.69 件**。交货时间更长，等货期间预计消耗更多，所以 ROP 也更高。 |
| original_eval × gpt-6-luna | IEDA-002-零基础 | 341 | 2 | 再订货点算错（应约为 19.23 件和 7.69 件） | 意思是：要覆盖 6 周等待期的预计需求，需要约 57.69 件库存。 |
| original_eval × gpt-6-luna | IEDA-002-零基础 | 342 | 3 | 再订货点算错（应约为 19.23 件和 7.69 件） | 因此，理论计算的再订货点是 **约 57.69 件**。 |

## 6. 待复核（needs_review）和失败 [Q9]

- general_v1 × gpt-6.1-sol：待复核 0 份，失败 0 份，未评 0 份
- original_eval × gpt-6.1-sol：待复核 0 份，失败 0 份，未评 0 份
- general_v1 × gpt-6-luna：待复核 0 份，失败 0 份，未评 0 份
- original_eval × gpt-6-luna：待复核 0 份，失败 0 份，未评 0 份

## 7. “清单外”备注（20 份）[Q10]

裁判以“清单外：”开头记下的清单以外的事实错误。不触发知识错误，不影响分数，供复核。

- general_v1 × gpt-6.1-sol：4 份
- original_eval × gpt-6.1-sol：0 份
- general_v1 × gpt-6-luna：5 份
- original_eval × gpt-6-luna：11 份

| 组 | 条目 | call | 第几次 | 备注 |
|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | COMP-001-有前置 | 35 | 2 | 清单外：推广部分假设 n 是任意正整数，但表格无条件列出指定 2 台、3 台空着的情形；当 n 小于相应数量时，这些情形不存在，表中的剩余选择数甚至可能为负。 |
| general_v1 × gpt-6-luna | COMP-001-零基础 | 214 | 1 | 清单外：讲解说属于三类不合格情况的分配在前两步后“被减过头”，实际上它被多留了一次，需再减去一次。 |
| general_v1 × gpt-6-luna | COMP-001-零基础 | 216 | 3 | 清单外：讲解说不合格分配“甚至三台服务器空着”，但五个任务都必须分配，三台服务器不可能全空；后文又正确地算出这种情况有0种。 |
| general_v1 × gpt-6.1-sol | COMP-001-零基础 | 31 | 1 | 清单外：一般证明中说配对的两组都会数到该函数，但如果指定不用的集合还包含该函数实际用到的输出，两组都不会数到它。应限定只配对由未使用输出组成的集合。 |
| original_eval × gpt-6-luna | COMP-001-零基础 | 306 | 3 | 清单外：讲解说“任务可以不止一个服务器接收”，与每个任务恰好分给一台服务器矛盾；例题中说“空着的服务器有 0 台：\(3^5\) 种”也不对，\(3^5\) 包含服务器空着的分法。 |
| original_eval × gpt-6-luna | COMP-003-有前置 | 321 | 3 | 清单外：“第 \(n\) 个新对象”应为新对象的第 \(n\) 个位置；不同的新对象分别避开对应的旧对象，不能保证某一个新对象避开整个列表。 |
| original_eval × gpt-6-luna | COMP-003-零基础 | 316 | 1 | 清单外：推广时说只要各位不同且新数属于目标集合即可，但小数表示可能不唯一；还需排除由无限多个9结尾导致的等值情况。 |
| original_eval × gpt-6-luna | COMP-003-零基础 | 318 | 3 | 清单外：讲解在“必须背”中把构造写成“第 n 个新对象的第 n 个位置”；这里实际构造的是一个新对象，而不是第 n 个新对象。 |
| original_eval × gpt-6-luna | ECON-001-有前置 | 277 | 1 | 清单外：讲解说利率太低时人们相对不愿持有货币、而更愿持有债券；这与利率降低会增加货币需求的关系相反。 |
| general_v1 × gpt-6-luna | ECON-002-有前置 | 194 | 2 | 清单外：讲解说产出增加时要维持均衡需要较高利率，这与其给出的向下倾斜条件及结论相矛盾；在这些条件下应需要较低利率。 |
| general_v1 × gpt-6.1-sol | ECON-002-零基础 | 8 | 2 | 清单外：“纵轴变量前的常数决定截距”表述有误：在纵轴变量已单独列出的函数式中，截距由右侧的常数项决定，而不是由纵轴变量前的系数决定。 |
| original_eval × gpt-6-luna | ECON-002-零基础 | 281 | 2 | 清单外：讲解说利率上升时沿 IS 曲线“向左下方移动”；在横轴为 Y、纵轴为 i 的图上，应为向左上方移动。 |
| general_v1 × gpt-6-luna | ECON-003-有前置 | 201 | 3 | 清单外：讲解说产出 Y 增加时，消费增加 c1Y、投资增加 b1Y；对于任意产出变化，增加量应分别是 c1ΔY 和 b1ΔY。另称新增产出合计大于最初支出变化，但当 c1+b1=0 时，两者相等。 |
| original_eval × gpt-6-luna | ECON-003-有前置 | 289 | 1 | 清单外：仅有 c1+b1<1 不足以保证等比数列收敛；还需要 c1+b1>−1，或者明确假定 c1、b1 非负。 |
| original_eval × gpt-6-luna | ECON-003-有前置 | 290 | 2 | 清单外：讲解说当 c1+b1 不小于 1 时“模型不会给出有限的乘数均衡”，但当 c1+b1 大于 1 时，等比级数虽不收敛，代数上的均衡解仍可能有限。 |
| general_v1 × gpt-6.1-sol | ECON-003-零基础 | 14 | 2 | 清单外：讲解说不满足 0≤c1+b1<1 时等比反馈不会逐渐消退，但若 c1+b1 在 -1 与 0 之间，反馈虽正负交替，仍会逐渐消退。 |
| original_eval × gpt-6-luna | ECON-003-零基础 | 286 | 1 | 清单外：讲解笼统地说乘数大于 1，但当 c1+b1=0 时，乘数等于 1。 |
| general_v1 × gpt-6-luna | ECON-005-有前置 | 212 | 2 | 清单外：讲解把 0.6Y 和 0.2Y 说成产出增加带来的消费和投资增量；它们是收入相关项，相应增量应分别为 0.6ΔY 和 0.2ΔY。 |
| original_eval × gpt-6-luna | IEDA-002-有前置 | 344 | 2 | 清单外：讲解称还需要额外说明在途订单等信息才能确定现有库存触发点；在持续按周期补货的稳态下，在途订单数量可由交货期和订货周期推得。 |
| original_eval × gpt-6-luna | IEDA-005-零基础 | 360 | 3 | 清单外：材料中的题目没有提到残值，讲解称“题目说的 residual value（残值）”有误。 |

## 8. gaps 的 severity 分布 [Q11]

条数（引句有效的；括号里是引句作废、不计入的条数）。每份平均 = 引句有效的条数 / ok 份数。

| 组 | 读者没法往下读 | 只是不顺 | 合计 | 每份平均 |
|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | 3 | 15 | 18 | 0.20 |
| original_eval × gpt-6.1-sol | 4 | 29 | 33 | 0.37 |
| general_v1 × gpt-6-luna | 22 | 44 | 66 | 0.73 |
| original_eval × gpt-6-luna | 19 | 55 | 74 | 0.82 |

按类型（引句有效的；读者没法往下读 / 只是不顺）：

| 组 | 公式未接含义 | 切换处漏连接 | 前提未交代 | 术语未先定义 |
|---|---|---|---|---|
| general_v1 × gpt-6.1-sol | 1 / 2 | 2 / 8 | 0 / 1 | 0 / 4 |
| original_eval × gpt-6.1-sol | 1 / 4 | 3 / 6 | 0 / 0 | 0 / 19 |
| general_v1 × gpt-6-luna | 6 / 7 | 11 / 16 | 4 / 5 | 1 / 16 |
| original_eval × gpt-6-luna | 5 / 11 | 11 / 11 | 3 / 6 | 0 / 27 |

## 8b. ECON-003 按新条目重判前后 [Q12]

- ECON-003 当前回答 24 份；按新条目判过的 24 份；有旧判分可比的 18 份（没有旧判分的是条目改动后才生成的回答）。旧判分保留在库里，不进上面任何统计。
- 知识判断变了的 2 份；卡点分变了的 2 份；步骤分变了的 16 份。

| 组 | 条目 | call | 第几次 | 知识（旧 → 新） | 卡点分（旧 → 新） | 步骤分（旧 → 新） | 旧 which |
|---|---|---|---|---|---|---|---|
| general_v1 × gpt-6-luna | ECON-003-有前置 | 199 | 1 | 通过 → 通过 | 1/2 → 1/2 | 1/3 → 2/3 |  |
| general_v1 × gpt-6-luna | ECON-003-有前置 | 200 | 2 | 通过 → 通过 | 1/2 → 1/2 | 1/3 → 2/3 |  |
| general_v1 × gpt-6-luna | ECON-003-有前置 | 201 | 3 | **不通过** → 通过 ⚑ | 0/2 → 1/2 | 0/3 → 2/3 | 乘数或其条件说错（应为 0 < c1 + b1 < 1 时乘数大于 1） |
| general_v1 × gpt-6.1-sol | ECON-003-有前置 | 16 | 1 | 通过 → 通过 | 2/2 → 2/2 | 1/3 → 2/3 |  |
| general_v1 × gpt-6.1-sol | ECON-003-有前置 | 17 | 2 | 通过 → 通过 | 2/2 → 2/2 | 1/3 → 2/3 |  |
| general_v1 × gpt-6.1-sol | ECON-003-有前置 | 18 | 3 | 通过 → 通过 | 2/2 → 2/2 | 2/3 → 2/3 |  |
| original_eval × gpt-6-luna | ECON-003-有前置 | 289 | 1 | — → 通过 | — → 2/2 | — → 2/3 |  |
| original_eval × gpt-6-luna | ECON-003-有前置 | 290 | 2 | — → 通过 | — → 2/2 | — → 2/3 |  |
| original_eval × gpt-6-luna | ECON-003-有前置 | 291 | 3 | — → 通过 | — → 1/2 | — → 2/3 |  |
| original_eval × gpt-6.1-sol | ECON-003-有前置 | 109 | 1 | **不通过** → 通过 ⚑ | 0/2 → 2/2 | 0/3 → 3/3 | 乘数或其条件说错（应为 0 < c1 + b1 < 1 时乘数大于 1） |
| original_eval × gpt-6.1-sol | ECON-003-有前置 | 110 | 2 | 通过 → 通过 | 2/2 → 2/2 | 2/3 → 3/3 |  |
| original_eval × gpt-6.1-sol | ECON-003-有前置 | 111 | 3 | 通过 → 通过 | 2/2 → 2/2 | 1/3 → 2/3 |  |
| general_v1 × gpt-6-luna | ECON-003-零基础 | 196 | 1 | 通过 → 通过 | 1/2 → 1/2 | 3/5 → 4/5 |  |
| general_v1 × gpt-6-luna | ECON-003-零基础 | 197 | 2 | 通过 → 通过 | 1/2 → 1/2 | 3/5 → 4/5 |  |
| general_v1 × gpt-6-luna | ECON-003-零基础 | 198 | 3 | 通过 → 通过 | 1/2 → 1/2 | 3/5 → 4/5 |  |
| general_v1 × gpt-6.1-sol | ECON-003-零基础 | 13 | 1 | 通过 → 通过 | 1/2 → 1/2 | 3/5 → 4/5 |  |
| general_v1 × gpt-6.1-sol | ECON-003-零基础 | 14 | 2 | 通过 → 通过 | 2/2 → 2/2 | 3/5 → 4/5 |  |
| general_v1 × gpt-6.1-sol | ECON-003-零基础 | 15 | 3 | **不通过** → **不通过** | 0/2 → 0/2 | 0/5 → 0/5 | 乘数或其条件说错（应为 0 < c1 + b1 < 1 时乘数大于 1） |
| original_eval × gpt-6-luna | ECON-003-零基础 | 286 | 1 | — → 通过 | — → 1/2 | — → 4/5 |  |
| original_eval × gpt-6-luna | ECON-003-零基础 | 287 | 2 | — → 通过 | — → 2/2 | — → 3/5 |  |
| original_eval × gpt-6-luna | ECON-003-零基础 | 288 | 3 | — → 通过 | — → 2/2 | — → 4/5 |  |
| original_eval × gpt-6.1-sol | ECON-003-零基础 | 106 | 1 | 通过 → 通过 | 1/2 → 1/2 | 3/5 → 4/5 |  |
| original_eval × gpt-6.1-sol | ECON-003-零基础 | 107 | 2 | 通过 → 通过 | 1/2 → 1/2 | 3/5 → 4/5 |  |
| original_eval × gpt-6.1-sol | ECON-003-零基础 | 108 | 3 | 通过 → 通过 | 1/2 → 1/2 | 3/5 → 4/5 |  |

⚑ = 知识判断变了。

## 9. 裁判稳定性：抽 30 份判第二遍 [Q13]

- 抽样：第一遍 ok 的当前回答，按课程分层，每门课 10 份；随机种子 20261111；judge_run R20261111-113334-aecf。
- 第二遍 30 份：ok 30，待复核 0，失败 0；两遍都 ok、可以比较的 30 份。

| 项目 | 比较单位 | 一致 / 总数 | 一致率 | Cohen's kappa |
|---|---|---|---|---|
| 知识（通过 / 不通过） | 每份回答 | 30 / 30 | 100.0% | — |
| 卡点（答上 / 没答上） | 每个卡点问题 | 51 / 52 | 98.1% | 0.90 |
| 步骤（踩中 / 没踩中） | 每个推荐步骤 | 102 / 104 | 98.1% | 0.94 |
| 卡点分完全相同 | 每份回答 | 29 / 30 | 96.7% | |
| 步骤分完全相同 | 每份回答 | 30 / 30 | 100.0% | |
| 没答全（附带） | 每份回答 | 30 / 30 | 100.0% | — |

卡点、步骤按第一遍判过的每个问题、每个步骤逐个比较（裁判看到的是同一份讲解、同一份请求）。kappa 在两遍几乎全是同一个值时会很低或算不出，要和一致率一起看。

按课程：

| 课程 | 份数 | 知识一致 | 卡点一致 | 步骤一致 |
|---|---|---|---|---|
| COMP2711 | 10 | 10/10 | 17/17 | 33/33 |
| ECON1221 | 10 | 10/10 | 15/15 | 40/42 |
| IEDA1280 | 10 | 10/10 | 19/20 | 29/29 |

两遍不一致的地方（3 处；1 = 通过/答上/踩中）：

| call | 条目 | 项 | 第一遍 | 第二遍 |
|---|---|---|---|---|
| 158 | IEDA-001-有前置 | q2 | 0 | 1 |
| 184 | ECON-001-零基础 | s1 | 0 | 1 |
| 184 | ECON-001-零基础 | s5 | 1 | 0 |

## 10. COMP 的 original_eval 回答：要文件路径、“待原题补齐”“非历年真题” [Q14]

COMP 的 original_eval 当前回答共 60 份。“要文件路径”按正则 `(文件|PDF|pdf|本地)?路径|上传|请(你)?(提供|发送|发来|给出|贴出)[^。\n]{0,12}(文件|PDF|pdf|原题|题目|试卷)` 匹配，命中的原句列在下面供核对；另两项是原文逐字查找。

| 项目 | 份数 | 次数 | 命中的回答（call） |
|---|---|---|---|
| 要文件路径 | 0 | 0 | — |
| 待原题补齐 | 0 | 0 | — |
| 非历年真题 | 2 | 2 | 304, 308 |

| 项目 | call | 条目 | 上下文 |
|---|---|---|---|
| 非历年真题 | 308 | COMP-001-有前置 | k)^m\)。  ### ③ 例题拆解  1. **题干**：来自你提供的材料，非历年真题（未提供年份、卷别、题号、分值或 PDF 页）。      “In how ma |
| 非历年真题 | 304 | COMP-001-零基础 | 数。  ### ③ 真题拆解  1. **题干**：以下是材料中提供的例题，**非历年真题**：      “In how many ways can 5 differe |

## 11. 实际花费 [Q15]

单价（每百万 tokens）：输入 $1.0，缓存输入 $0.05，输出 $5.0。“计缓存折扣”只用每条记录最后一次调用报告的缓存 tokens；重判过的记录前几次调用的缓存不知道，按标价算，所以是上限。

| judge_run | 用途 | 记录数 | 其中调用多次的 | 输入 tokens | 其中缓存（最后一次） | 输出 tokens | 标价 | 计缓存折扣 |
|---|---|---|---|---|---|---|---|---|
| J20261111-111709-e967 | main | 5 | 0 | 22,246 | 15,876 | 8,254 | $0.064 | $0.048 |
| J20261111-112302-67ef | main | 265 | 3 | 1,053,192 | 596,171 | 368,131 | $2.894 | $2.327 |
| R20261111-113334-aecf | repeat | 30 | 0 | 119,687 | 119,597 | 44,736 | $0.343 | $0.230 |
| J20261111-121814-c71a | main | 18 | 0 | 84,476 | 37,740 | 29,455 | $0.232 | $0.196 |
| J20261111-124414-e0df | main | 90 | 1 | 333,785 | 200,436 | 136,997 | $1.019 | $0.828 |
| **合计** | | | | 1,613,386 | 969,820 | 587,573 | **$4.551** | **$3.630** |

验收样例（fixture_judgments）不在这张表里，第 6 节已单独报过。

## 附录：SQL

**Q1. 各组份数：当前回答、ok、待复核、失败、未评**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT grp, count(*) AS n, coalesce(sum(status = 'ok'), 0) AS n_ok,
       coalesce(sum(status = 'needs_review'), 0) AS n_review, coalesce(sum(status = 'error'), 0) AS n_error,
       sum(judgment_id IS NULL) AS n_unjudged
FROM sel GROUP BY grp
```

**Q2. 各组主要结果（按回答平均，只算 ok）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT grp, count(*) AS n_ok,
       avg(knowledge_pass) AS k_pass, sum(knowledge_pass = 0) AS n_k_fail,
       avg(incomplete) AS incomplete, sum(incomplete) AS n_incomplete,
       avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step,
       avg(gate_all) AS gate_all
FROM sel WHERE status = 'ok' GROUP BY grp
```

**Q3. 各组卡点分、步骤分（按条目平均，只算 ok）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
),
per_item AS (
  SELECT grp, item_id, avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step,
         avg(knowledge_pass) AS k_pass, avg(incomplete) AS incomplete
  FROM sel WHERE status = 'ok' GROUP BY grp, item_id)
SELECT grp, count(*) AS n_items, avg(k_pass) AS k_pass, avg(incomplete) AS incomplete,
       avg(gate) AS gate, avg(step) AS step
FROM per_item GROUP BY grp
```

**Q4. 逐条目 × 组的卡点分、步骤分（条目内平均，只算 ok）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT item_id, grp, avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step
FROM sel WHERE status = 'ok' GROUP BY item_id, grp
```

**Q5. 卡点分分布（每份 ok 回答的 gate_num/gate_den）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT grp, round(1.0 * gate_num / gate_den, 3) AS v, sum(knowledge_pass = 0) AS n_k_fail, count(*) AS n
FROM sel WHERE status = 'ok' GROUP BY grp, v ORDER BY grp, v
```

**Q6. 步骤分分布（每份 ok 回答的 step_num/step_den，分 5 档）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT grp, CASE WHEN step_num = 0 THEN '0'
                 WHEN 1.0 * step_num / step_den < 0.5 THEN '(0, 0.5)'
                 WHEN 1.0 * step_num / step_den < 0.8 THEN '[0.5, 0.8)'
                 WHEN step_num < step_den THEN '[0.8, 1)'
                 ELSE '1' END AS bucket,
       sum(knowledge_pass = 0) AS n_k_fail, count(*) AS n
FROM sel WHERE status = 'ok' GROUP BY grp, bucket
```

**Q7. 逐条目 × 组（只算 ok）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT item_id, grp, count(*) AS n_ok, sum(knowledge_pass) AS n_k_pass, sum(incomplete) AS n_incomplete,
       avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step
FROM sel WHERE status = 'ok' GROUP BY item_id, grp ORDER BY item_id
```

**Q8. 知识不通过的回答**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT grp, item_id, call_id, repeat_idx,
       json_extract(parsed_json, '$.knowledge_error.which') AS which,
       json_extract(parsed_json, '$.knowledge_error.quotes') AS quotes
FROM sel WHERE status = 'ok' AND knowledge_pass = 0 ORDER BY item_id, grp, repeat_idx
```

**Q9. 待复核（needs_review）和失败（error）的回答**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT grp, item_id, call_id, repeat_idx, status, judgment_id, error
FROM sel WHERE status IN ('needs_review', 'error') OR judgment_id IS NULL ORDER BY status, item_id, grp
```

**Q10. “清单外”备注（knowledge_error.note 或 incomplete.note 以“清单外”开头）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT grp, item_id, call_id, repeat_idx, status,
       json_extract(parsed_json, '$.knowledge_error.note') AS k_note,
       json_extract(parsed_json, '$.incomplete.note') AS i_note
FROM sel WHERE status IN ('ok', 'needs_review')
  AND (ltrim(coalesce(json_extract(parsed_json, '$.knowledge_error.note'), '')) LIKE '清单外%'
    OR ltrim(coalesce(json_extract(parsed_json, '$.incomplete.note'), '')) LIKE '清单外%')
ORDER BY item_id, grp, repeat_idx
```

**Q11. gaps 的 severity 分布（只算 ok 回答）**

```sql
WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = 'gpt-6.1-terra'
         AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
)
SELECT sel.grp, g.severity, g.subtype, g.quote_valid, count(*) AS n
FROM sel JOIN judge_gaps g ON g.judgment_id = sel.judgment_id
WHERE sel.status = 'ok' GROUP BY sel.grp, g.severity, g.subtype, g.quote_valid
```

**Q12. 条目改动前后的裁判结果：同一份当前回答，旧判分清单的最新 ok 记录 vs 当前判分清单的最新 ok 记录**

```sql
SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
            ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
       c.id AS call_id, c.item_id, c.repeat_idx,
       o.id AS old_id, o.knowledge_pass AS k_old, o.gate_num AS g_old, o.gate_den AS gd_old,
       o.step_num AS s_old, o.step_den AS sd_old, json_extract(o.parsed_json, '$.knowledge_error.which') AS which_old,
       n.id AS new_id, n.knowledge_pass AS k_new, n.gate_num AS g_new, n.gate_den AS gd_new,
       n.step_num AS s_new, n.step_den AS sd_new, json_extract(n.parsed_json, '$.knowledge_error.which') AS which_new,
       json_extract(n.parsed_json, '$.knowledge_error.note') AS note_new
FROM current_calls c
JOIN items_snapshot s ON s.item_id = c.item_id
LEFT JOIN judgments n ON n.id = (
     SELECT max(x.id) FROM judgments x WHERE x.call_id = c.id AND x.status = 'ok'
       AND x.judge_model_name = 'gpt-6.1-terra' AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 = s.rubric_sha256)
LEFT JOIN judgments o ON o.id = (
     SELECT max(x.id) FROM judgments x WHERE x.call_id = c.id AND x.status = 'ok'
       AND x.judge_model_name = 'gpt-6.1-terra' AND x.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136' AND x.rubric_sha256 != s.rubric_sha256)
WHERE c.item_id LIKE 'ECON-003-%'
ORDER BY c.item_id, grp, c.repeat_idx
```

**Q13. 稳定性检查：第二遍（repeat_judgments）与第一遍（judgments）配对**

```sql
SELECT r.id AS repeat_id, r.judge_run_id, r.sample_seed, r.call_id, r.item_id, r.course, r.status AS r_status,
       j.id AS first_id, j.status AS j_status,
       j.knowledge_pass AS k1, r.knowledge_pass AS k2, j.incomplete AS i1, r.incomplete AS i2,
       j.gate_num AS g1, r.gate_num AS g2, j.gate_den AS gden, j.step_num AS s1, r.step_num AS s2, j.step_den AS sden,
       j.parsed_json AS p1, r.parsed_json AS p2
FROM repeat_judgments r JOIN judgments j ON j.id = r.first_judgment_id
JOIN items_snapshot s ON s.item_id = r.item_id   -- 只算当前条目文件里的条目（长请求等另一套条目不算）
WHERE r.judge_model_name = 'gpt-6.1-terra' AND r.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136'
ORDER BY r.call_id
```

**Q14. COMP 的 original_eval 当前回答（关键词在 Python 里匹配）**

```sql
SELECT c.id AS call_id, c.item_id, c.repeat_idx, c.skill_file, c.response_text
FROM current_calls c
WHERE c.skill_file LIKE 'skills/original_eval/%' AND c.item_id LIKE 'COMP-%'
ORDER BY c.item_id, c.repeat_idx
```

**Q15. 裁判花费：按 judge_run 汇总（这版 prompt 的正式评分和第二遍）**

```sql
SELECT jr.judge_run_id, coalesce(jr.purpose, 'main') AS purpose, jr.started_at, jr.finished_at,
       count(x.id) AS n_rows, sum(x.input_tokens) AS tin, sum(x.output_tokens) AS tout,
       sum(CASE WHEN x.attempts = 1 THEN 0 ELSE 1 END) AS n_multi,
       sum(coalesce(json_extract(x.usage_raw, '$.input_tokens_details.cached_tokens'), 0)) AS cached_last
FROM judge_runs jr
JOIN (SELECT id, judge_run_id, item_id, input_tokens, output_tokens, attempts, usage_raw FROM judgments
      UNION ALL
      SELECT id, judge_run_id, item_id, input_tokens, output_tokens, attempts, usage_raw FROM repeat_judgments) x
  ON x.judge_run_id = jr.judge_run_id
JOIN items_snapshot s ON s.item_id = x.item_id   -- 只算当前条目文件里的条目
WHERE jr.prompt_sha256 = '5e576469040012f66469e9d7d727f0ffe4b3972bd4c04ce959edba8a9efa3136'
GROUP BY jr.judge_run_id ORDER BY jr.started_at
```

