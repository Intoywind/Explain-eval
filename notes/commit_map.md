# 提交编号对照（改写历史前 → 后）

推送到 GitHub 之前用 `git filter-repo` 统一了作者信息、去掉了本机路径和一句与实验无关的话，所有提交的编号都变了。
文档（`docs/specs/`、`notes/ai_coding_log.md`、`reports/`）里写的是旧编号，按下表对应到新编号。

## 文档里引用过的旧编号

| 旧编号 | 新编号 | 提交说明 |
|---|---|---|
| `0826870` | `30232cb` | 加入通用 Skill v2 第五稿（md5 32ab9d6e…）和第六份输入 |
| `aa126b6` | `8de1363` | 通用 V2 在 30 条短题上试跑：生成 180 份、判分 180 份 + 20 份第二遍、V1 对 V2 报告和样例 |
| `9d62e9f` | `c7a2796` | 测试集草稿原样提交：长题、合并评测集（items_merged.jsonl md5 02c0dc26e61799b7d2f7547195f11bee）、对应表、生成脚本；第七份输入 |
| `7d7aebc` | `56a4bbc` | 正式测试：合并评测集 × 三份 Skill × 两个模型；长题生成 540 份、判分 540 份 + 54 份第二遍、计分模块和报告 |
| `cef6fc5` | `56d38f1` | 长请求验证：生成 36 份、裁判 36 份 + 12 份第二遍、单独报告 |
| `ca00b19` | `ac3e9f2` | 第 7 节：judge_v2 判全部三组、30 份第二遍稳定性检查、三组汇总 |
| `04fefb6` | `8ffc997` | 第四组 original_eval × gpt-6-luna、ECON-003 按新条目重判、四组汇总、正式盲标包抽样 |

## 全部提交（按时间先后）

| # | 旧编号 | 新编号 | 提交说明 |
|---|---|---|---|
| 1 | `64fde2d` | `e56b164` | 搭建评测项目骨架和批量运行（不含自动评分） |
| 2 | `2162382` | `ad63c1a` | config：gpt-6.1-sol 写死 reasoning.effort=medium，temperature 用接口默认值 |
| 3 | `ba5f483` | `125e672` | 更新判分清单，加入 original_eval 测试用 Skill 副本 |
| 4 | `ffae021` | `d7e253e` | 续跑改用请求哈希；支持 --skill original_eval |
| 5 | `2c82bfd` | `6e87867` | config：加入 gpt-6-luna，固定 reasoning.effort 和 text.verbosity 为 medium |
| 6 | `893172e` | `6d825b7` | 提交两份输入说明的更新和裁判 prompt judge_v1.md |
| 7 | `7478530` | `a15f9e8` | 第二轮：裁判、规则检查、盲打、人和裁判对比、Skill 比较报告；没有有效证据不清零 |
| 8 | `9c91b3d` | `2d8fbab` | 条目 ECON-001 修订、裁判 prompt judge_v2、第三份输入说明 |
| 9 | `a5c7a93` | `52d32aa` | 裁判验收样例与第 6 节验收；报告按三组列待复核 |
| 10 | `ca00b19` | `ac3e9f2` | 第 7 节：judge_v2 判全部三组、30 份第二遍稳定性检查、三组汇总 |
| 11 | `4b29ab2` | `800c165` | 条目 ECON-003 修订：知识错误清单措辞、“交代公式成立的条件”步骤措辞 |
| 12 | `04fefb6` | `8ffc997` | 第四组 original_eval × gpt-6-luna、ECON-003 按新条目重判、四组汇总、正式盲标包抽样 |
| 13 | `fe8f4f5` | `5e33a31` | 长请求验证：条目文件、拼接脚本、对应表、第四份输入；schema 接受“长请求” |
| 14 | `cef6fc5` | `56d38f1` | 长请求验证：生成 36 份、裁判 36 份 + 12 份第二遍、单独报告 |
| 15 | `0826870` | `30232cb` | 加入通用 Skill v2 第五稿（md5 32ab9d6e…）和第六份输入 |
| 16 | `aa126b6` | `8de1363` | 通用 V2 在 30 条短题上试跑：生成 180 份、判分 180 份 + 20 份第二遍、V1 对 V2 报告和样例 |
| 17 | `9d62e9f` | `c7a2796` | 测试集草稿原样提交：长题、合并评测集（items_merged.jsonl md5 02c0dc26e61799b7d2f7547195f11bee）、对应表、生成脚本；第七份输入 |
| 18 | `7d7aebc` | `56a4bbc` | 正式测试：合并评测集 × 三份 Skill × 两个模型；长题生成 540 份、判分 540 份 + 54 份第二遍、计分模块和报告 |
| 19 | `40a745b` | `dfc2cc4` | 补交草稿存档、删改清单和第五份输入 |
| 20 | `dd7fa4e` | `693c0ac` | 去掉本机路径：换成 <本机课程资料目录>/ |
| 21 | `c4a0bf0` | `aa85fb8` | 七份输入挪进 docs/specs/（文件名不变） |

完整的 40 位编号：

```
64fde2db8fa7c2ab537c56ebc7da9c4aa24f8059 e56b16483529144882f9b981425757bd90000e0e
21623829ca3ae641aea4035f4fbcb6db894173b0 ad63c1a763129e5ddb6305724df0c839334ac305
ba5f483a0b5746bc2dba1708ca30c5d8b93f0d98 125e672fbad52b9206d89168ff2bb7f4c00531c7
ffae021d7cdfa351eef631fcf49b2dcd43483e53 d7e253e789347cc34f3d795de5a622a55a3d6e2a
2c82bfd03a9f2d39e838e95c1011b88e87f3b984 6e878671b25597c4e4822434d664dfbd183a0499
893172e47ac81fd848b9bebf1ac5dcadad20656a 6d825b7c24c5c06cd41c4f590483dadfb1fe412c
74785304dae7a245caea2cba412dd9a86caeb881 a15f9e83ddb624508ceeee452778d614035f7568
9c91b3d0fcc9378b01c0d7898cd78e98c0fb403a 2d8fbab0f5e54c981592ada72f25dc195c8d1a49
a5c7a93aa7352ec18ca490ddf77c76181dd04af8 52d32aad5bed63fb957ebc3c2e37b050e1e97e47
ca00b19babfacc8a10cb7aa3979a68d1b228b952 ac3e9f2a4abda3b7e17094ce1acf42c1afc9e6b3
4b29ab281cab74953b69843cfc14b923069d577e 800c16542882342b35851e8e61d751050b6d3145
04fefb68aa5fce1ae7e69953649d5ac2cd6fbe13 8ffc9976a9b532a7351d8a167129d61c5eeca689
fe8f4f5f85e9fb5ac521fe330987660070e5a318 5e33a31f15d6f130c0749c90a5a6752e73a92169
cef6fc52be013d358ef921c956c84b788fa5e624 56d38f10985f62cdbac3d5aaa3e3174a3a963257
08268709e2e9f67a46c62a68d01077bd7781762f 30232cbdc3085027feb2bb1b76128f049b394b28
aa126b62908da287b03d6573aa2768127f35f816 8de1363203e7cb5d80970bd0528ff09a5b02e7b7
9d62e9fe7bc9d62b28e36a7c9eeb58a421259d20 c7a2796194311bfbbf1a60471989bd3f24ac2154
7d7aebc1639076329461ca6043d2abd329151ead 56a4bbcb1aa1674fe6ddf179291c5c69f319f901
40a745b14897a99243128cf5978079e267716ef6 dfc2cc4c4087957e2d12d323b7e847ac3e615c7d
dd7fa4e0aa78ef7a0303b5bbc106a0de7db3ec6f 693c0ac834cec9b28e66ddb4e249a927e1815fd3
c4a0bf05dcfbe32db27e6bd52cd6ec808e5b309c aa85fb88b13c16948d1e9611d965c75eafef2d30
```
