# 六年级数学应用题金标准模板

## 目录

- [1. 文档目标](#1-文档目标)
- [2. 首批题型范围](#2-首批题型范围)
- [3. 金标准文件结构](#3-金标准文件结构)
- [4. 通用题目金标准模板](#4-通用题目金标准模板)
- [5. 各题型专属建模要求](#5-各题型专属建模要求)
  - [5.1 和差问题](#51-和差问题)
  - [5.2 倍数问题](#52-倍数问题)
  - [5.3 分数问题](#53-分数问题)
  - [5.4 百分数问题](#54-百分数问题)
  - [5.5 行程问题](#55-行程问题)
  - [5.6 工程问题](#56-工程问题)
  - [5.7 年龄问题](#57-年龄问题)
- [6. 学生步骤样本模板](#6-学生步骤样本模板)
- [7. 多轮教学对话模板](#7-多轮教学对话模板)
- [8. 理解验证模板](#8-理解验证模板)
- [9. 完整填写示例：百分数问题](#9-完整填写示例百分数问题)
- [10. 标注与审核规范](#10-标注与审核规范)
- [11. MVP 建议数据规模](#11-mvp-建议数据规模)
- [12. 相关文档](#12-相关文档)

## 1. 文档目标

本模板用于建设六年级数学应用题的金标准数据，支持：

- 题目结构化和题型识别。
- 生成并验证 1～2 条适龄参考解法。
- 建立题目对象、数量关系和解题步骤图。
- 将学生口语表达对齐到具体步骤和对象。
- 判断学生步骤正确、错误、部分正确或无法确认。
- 为教学状态机提供下一最小教学目标。
- 检查 AI 回复是否数学正确、是否提示过量。
- 评测学生是否真正理解核心数量关系。

金标准主要用于离线评测、模型选型和版本回归。内部标准答案与完整解法不能直接展示给尚未独立作答的学生。

## 2. 首批题型范围

| 题型 | 核心数量关系 | 需要特别关注的对象 |
| --- | --- | --- |
| 和差问题 | 大数 + 小数 = 总数；大数 − 小数 = 相差数 | 大数、小数、总数、相差数 |
| 倍数问题 | 一个量 = 倍数 × 另一个量 | 标准量、比较量、倍数 |
| 分数问题 | 单位“1” × 分率 = 对应量 | 单位“1”、分率、对应量 |
| 百分数问题 | 原价 × 百分率 = 对应金额 | 原价、百分率、现价、优惠额或涨价额 |
| 行程问题 | 速度 × 时间 = 路程 | 运动对象、方向、速度、时间、路程 |
| 工程问题 | 工作效率 × 时间 = 工作量 | 工作者、总工作量、效率、时间 |
| 年龄问题 | 同一人的年龄随时间等量变化；年龄差保持不变 | 人物、当前年龄、时间偏移、年龄差或倍数 |

首批数据应优先选择：

- 条件完整、答案明确的单问应用题。
- 能用六年级常见方法解决的题目。
- 数量不复杂，但能暴露概念错误的题目。
- 不依赖超纲方程、复杂几何或隐藏常识的题目。

## 3. 金标准文件结构

建议使用 YAML，便于人工审核；程序加载后转换为 JSON Schema 校验。

```text
evaluation/
├── schema/
│   ├── grade6-word-problem.schema.json
│   ├── student-step.schema.json
│   └── tutoring-dialogue.schema.json
├── cases/
│   ├── sum-difference/
│   ├── multiples/
│   ├── fractions/
│   ├── percentages/
│   ├── motion/
│   ├── work-rate/
│   └── ages/
├── student-steps/
├── conversations/
└── rubrics/
    ├── math-correctness.yaml
    ├── step-alignment.yaml
    ├── teaching-action.yaml
    └── answer-leakage.yaml
```

推荐 ID 规则：

```text
g6-{题型}-{四位序号}

示例：
g6-percentage-0001
g6-motion-0008
g6-age-0012
```

## 4. 通用题目金标准模板

下面是一道题对应的主文件模板。没有使用的字段填 `null` 或删除，但核心字段不得省略。

```yaml
schema_version: "1.0"
case_id: "g6-{problem_type}-{number}"
status: "draft | reviewed | approved | deprecated"

scope:
  subject: "数学"
  grade: "六年级"
  domain: "应用题"
  problem_type: "sum_difference | multiple | fraction | percentage | motion | work_rate | age"
  subtype: "具体子类型"
  difficulty: "basic | intermediate | advanced"
  curriculum_tags: []

source:
  origin: "original | licensed | adapted"
  source_reference: null
  copyright_status: "cleared"

problem:
  text: "完整题目文本"
  question: "题目要求求什么"
  answer_form: "number | quantity_with_unit | expression | explanation"
  has_irrelevant_information: false
  has_implicit_condition: false
  implicit_conditions: []

objects:
  - object_id: "唯一对象 ID"
    name: "对象名称"
    type: "person | amount | price | distance | speed | time | work | age | other"
    owner: null
    value: null
    unit: null
    role: "given | unknown | intermediate"
    source_span: "来自题目中的原文"

relationships:
  - relationship_id: "r1"
    type: "sum | difference | multiple | fraction_of | percentage_of | distance_formula | work_formula | age_shift"
    natural_language: "用自然语言说明关系"
    expression: "结构化数学表达"
    operands: []
    result: "对象 ID"
    required_conditions: []

unit_one:
  required: false
  object_id: null
  evidence: null

answer:
  final_value: null
  unit: null
  accepted_forms: []
  validation_expression: "用于代回或验证的表达式"
  internal_only: true

solution_paths:
  - path_id: "path_1"
    method: "方法名称"
    age_appropriate: true
    priority: 1
    prerequisites: []
    steps:
      - step_id: "p1_s1"
        depends_on: []
        goal: "这一步的教学目标"
        action: "identify | define | add | subtract | multiply | divide | build_relation | solve | check"
        input_objects: []
        output_object: null
        expression_before: null
        operation: "进行的数学操作"
        expression_after: null
        result_value: null
        unit: null
        required_understanding: "学生需要理解的原因"
        allowed_hint_levels:
          L1: "只提醒相关概念"
          L2: "聚焦关键条件"
          L3: "提示方法方向"
          L4: "拆出当前小步骤"
        forbidden_before_student_attempt: []
        verification:
          tool: "sympy | pint | rule | llm_reviewer"
          assertion: "可执行或可审核的验证条件"

solution_graph:
  nodes:
    - node_id: "节点 ID"
      label: "步骤名称"
      object_ids: []
  edges:
    - from: "前置节点"
      to: "后续节点"
  branch_rules: []

common_errors:
  - error_id: "e1"
    type: "reading | relation | unit_one | operation | sign | unit | object_binding | time_shift"
    student_expression: "典型错误表达"
    first_error_span: "第一个错误位置"
    misconception: "错误背后的可能原因"
    diagnostic_question: "用于确认错误原因的问题"
    preferred_teaching_action: "对应教学动作"

teaching_boundaries:
  before_student_final_attempt:
    allowed: []
    forbidden: []
  after_student_final_attempt:
    allowed: []
    forbidden: []

understanding_checks:
  explain_why:
    prompt: "让学生解释关键关系的问题"
    key_elements: []
    common_weak_answers: []
  error_detection:
    prompt: "让学生识别典型错误的问题"
    error_example: "错误算式或理由"
    expected_explanation: "期望解释"
  micro_transfer:
    prompt: "轻量变式问题"
    expected_answer: "变式答案"
    changed_core_feature: "变化的核心关系"

review:
  math_reviewer: null
  pedagogy_reviewer: null
  reviewed_at: null
  tool_verification_passed: false
  notes: null
```

## 5. 各题型专属建模要求

### 5.1 和差问题

#### 典型关系

```text
大数 + 小数 = 总数
大数 - 小数 = 相差数

大数 = (总数 + 相差数) ÷ 2
小数 = (总数 - 相差数) ÷ 2
```

#### 必须标注的对象

- 大数所代表的实际对象。
- 小数所代表的实际对象。
- 总数。
- 相差数。
- 题目要求求大数、小数，还是两者。

#### 常见错误

- 将总数和相差数混淆。
- 求小数时使用 `(总数 + 相差数) ÷ 2`。
- 只计算一次，没有求出题目要求的另一个量。
- 算式正确，但把结果绑定到相反对象。

#### 专属字段示例

```yaml
type_specific:
  larger_object_id: "large_amount"
  smaller_object_id: "small_amount"
  total_object_id: "total_amount"
  difference_object_id: "difference"
  relationship_expressions:
    - "large_amount + small_amount = total_amount"
    - "large_amount - small_amount = difference"
```

### 5.2 倍数问题

#### 典型关系

```text
比较量 = 标准量 × 倍数
标准量 = 比较量 ÷ 倍数
倍数 = 比较量 ÷ 标准量
```

#### 必须标注的对象

- 谁是“1 倍量”或标准量。
- 谁是比较量。
- 倍数是否包含原来的 1 倍。
- 题目是在求量，还是求倍数。

#### 常见错误

- 把标准量和比较量颠倒。
- 将“多 3 倍”与“是 3 倍”混淆。
- 应使用乘法时错误使用加法。
- 正确算出数值，但解释不了倍数对应谁。

#### 专属字段示例

```yaml
type_specific:
  base_object_id: "base_amount"
  compared_object_id: "compared_amount"
  multiplier: 3
  phrase_type: "is_times | more_than_by_times"
  normalized_relationship: "compared_amount = base_amount * 3"
```

### 5.3 分数问题

#### 典型关系

```text
单位“1” × 分率 = 对应量
单位“1” = 对应量 ÷ 分率
分率 = 对应量 ÷ 单位“1”
```

#### 必须标注的对象

- 单位“1”是谁。
- 分率描述的是哪个量占哪个量。
- 已知的是单位“1”、对应量，还是分率。
- 分率是否经过增加或减少。

#### 常见错误

- 找错单位“1”。
- 看到分数就直接乘，没有判断未知量。
- 将“比单位 1 多几分之几”误写成只乘该分率。
- 分率的分子、分母或作用对象绑定错误。

#### 专属字段示例

```yaml
type_specific:
  unit_one_object_id: "total_books"
  corresponding_object_id: "read_books"
  fraction: "3/5"
  normalized_relationship: "read_books = total_books * 3/5"
```

### 5.4 百分数问题

#### 典型关系

```text
原价 × 折扣率 = 现价
原价 × 优惠率 = 优惠金额
原价 × (1 - 优惠率) = 现价
原数量 × (1 + 增长率) = 增长后数量
原数量 × (1 - 减少率) = 减少后数量
```

“原价 × 百分率”中的百分率必须说明是折扣率、优惠率、增长率还是剩余率，不能只保存一个模糊的 percentage 字段。

#### 必须标注的对象

- 原始量或单位“1”。
- 百分率的语义。
- 百分率对应的部分量。
- 求的是现价、优惠额、增长额还是变化后的总量。

#### 常见错误

- 将优惠率直接当成现价率。
- `20%` 错写成 `20`。
- “打八折”与“优惠 80%”混淆。
- 连续变化时直接相加百分率。

#### 专属字段示例

```yaml
type_specific:
  base_object_id: "original_price"
  percentage: "20%"
  percentage_role: "discount_amount_rate"
  target_object_id: "sale_price"
  normalized_relationship: "sale_price = original_price * (1 - 20%)"
```

### 5.5 行程问题

#### 典型关系

```text
速度 × 时间 = 路程
路程 ÷ 时间 = 速度
路程 ÷ 速度 = 时间
```

#### 必须标注的对象

- 每个运动对象。
- 运动方向：同向、相向、相背或往返。
- 每个对象对应的速度、时间和路程。
- 同时出发、先后出发等时间关系。
- 相遇、追及或到达等事件条件。

#### 常见错误

- 相向运动使用速度差。
- 追及问题使用速度和。
- 将不同对象的速度和路程混合绑定。
- 忽略先出发造成的时间差。
- 单位没有统一。

#### 专属字段示例

```yaml
type_specific:
  motion_mode: "opposite | same_direction | away | round_trip"
  event: "meet | catch_up | arrive"
  travelers:
    - object_id: "traveler_a"
      speed_object_id: "speed_a"
      time_object_id: "time_a"
      distance_object_id: "distance_a"
    - object_id: "traveler_b"
      speed_object_id: "speed_b"
      time_object_id: "time_b"
      distance_object_id: "distance_b"
  event_relationship: "distance_a + distance_b = total_distance"
```

### 5.6 工程问题

#### 典型关系

```text
工作效率 × 时间 = 工作量
工作量 ÷ 时间 = 工作效率
工作量 ÷ 工作效率 = 时间

总工作量通常可以设为单位“1”
```

#### 必须标注的对象

- 总工作量是否设为单位“1”。
- 每个工作者或设备。
- 独立工作时间和对应效率。
- 合作阶段与单独阶段。
- 效率是否保持不变。

#### 常见错误

- 将完成时间直接相加。
- 合作时使用效率差而不是效率和。
- 忘记总工作量设为单位“1”。
- 把“还剩多少”与“已经完成多少”混淆。

#### 专属字段示例

```yaml
type_specific:
  total_work_object_id: "total_work"
  total_work_normalized_value: 1
  workers:
    - object_id: "worker_a"
      solo_time: 6
      efficiency_expression: "1/6"
    - object_id: "worker_b"
      solo_time: 3
      efficiency_expression: "1/3"
  combined_efficiency_expression: "1/6 + 1/3"
```

### 5.7 年龄问题

#### 典型关系

```text
未来年龄 = 当前年龄 + 经过年数
过去年龄 = 当前年龄 - 经过年数
两人的年龄差随时间保持不变
```

#### 必须标注的对象

- 每个人物。
- 当前、过去或未来的时间点。
- 时间偏移量。
- 每个时间点对应的年龄。
- 年龄差或倍数关系出现在哪个时间点。

#### 常见错误

- 只给一个人的年龄增加时间。
- 将年龄倍数误认为始终不变。
- 把“几年前”和“几年后”的符号弄反。
- 将当前年龄关系错误绑定到未来时间点。

#### 专属字段示例

```yaml
type_specific:
  people:
    - object_id: "parent"
      current_age_object_id: "parent_age_now"
    - object_id: "child"
      current_age_object_id: "child_age_now"
  time_offset:
    value: 5
    direction: "future"
  invariant_relationship: "parent_age - child_age = constant"
  timed_relationship: "parent_age_now + 5 = 2 * (child_age_now + 5)"
```

## 6. 学生步骤样本模板

每道题建议至少包含正确、错误、部分正确、含糊和新解法五类学生表达。

```yaml
sample_id: "{case_id}-step-{number}"
case_id: "对应题目 ID"

conversation_state:
  teaching_state: "probe | diagnose | hint | verify_step | final_attempt | transfer_check"
  active_solution_path: "path_1 | unknown | student_new_path"
  completed_step_ids: []
  current_step_candidates: []
  current_focus_objects: []
  hint_level: 0
  student_final_answer_submitted: false

student_input:
  raw_text: "学生原始表达"
  normalized_math: null
  referenced_screen_targets: []

gold_alignment:
  candidate_steps:
    - step_id: "候选步骤 ID"
      object_ids: []
      score: 0.0
      evidence: []
  verdict: "aligned | ambiguous | new_valid_path | unverifiable"
  selected_step_id: null
  alignment_confidence: 0.0

gold_judgment:
  intent: []
  verdict: "correct | incorrect | partially_correct | unverifiable"
  mathematical_result_correct: null
  object_binding_correct: null
  first_error_span: null
  error_type: null
  demonstrated_understanding: []
  missing_understanding: []
  misconception: null
  next_subgoal: "下一最小教学目标"

allowed_actions: []
forbidden_actions: []
forbidden_content: []

acceptable_response_examples:
  - "一个合格参考回复"

unacceptable_response_examples:
  - text: "一个不合格回复"
    reasons: []
```

## 7. 多轮教学对话模板

```yaml
conversation_id: "{case_id}-conversation-{number}"
case_id: "对应题目 ID"
scenario: "本对话要覆盖的学生行为"

initial_state:
  teaching_state: "probe"
  hint_level: 0
  completed_step_ids: []
  revealed_solution_steps: []
  student_final_answer_submitted: false

turns:
  - turn: 1
    student:
      raw_text: "学生表达"
      voice_features:
        incomplete_utterance: false
        self_correction: false
    gold:
      intents: []
      aligned_step_id: null
      verdict: null
      next_state: "下一个教学状态"
      next_subgoal: "下一最小教学目标"
      allowed_actions: []
      forbidden_actions: []
      required_elements: []
      forbidden_content: []
      state_updates: []
      reference_response: "一个合格的参考回复"

  - turn: 2
    student:
      raw_text: "下一轮学生表达"
    gold:
      intents: []
      next_state: "..."
      reference_response: "..."

final_expectation:
  answer_submitted_by_student: true
  understanding_check_required: true
  acceptable_understanding_status:
    - "basic_understanding"
    - "transfer_confirmed"
```

建议多轮场景覆盖：

- 学生完全无思路。
- 学生使用错误数量关系。
- 学生答对但无法解释单位“1”。
- 学生跳过中间步骤。
- 学生使用不同于参考解法的方法。
- 学生反复索要答案。
- 学生说到一半停顿，随后继续。
- 学生指出 AI 的数学错误。
- 学生在较强提示下完成，但变式题失败。

## 8. 理解验证模板

理解验证应围绕题型的核心数量关系，而不是只替换无关数字。

```yaml
understanding_evaluation:
  case_id: "题目 ID"
  student_id: "匿名测试编号"

  evidence:
    final_answer:
      result: "passed | failed"
    independent_key_step:
      result: "passed | failed"
      step_id: "关键步骤 ID"
    explain_why:
      result: "passed | partial | failed | not_tested"
      evidence_text: "学生解释"
    error_detection:
      result: "passed | partial | failed | not_tested"
    micro_transfer:
      result: "passed | partial | failed | not_tested"

  hint_dependency:
    max_hint_level: 0
    key_steps_completed_independently: 0

  unresolved_misconceptions: []

  result:
    status: "needs_learning | completed_with_support | basic_understanding | transfer_confirmed"
    confidence: 0.0
    reasons: []
    next_action: "continue | summarize | schedule_review"
```

各题型建议验证重点：

| 题型 | 理解验证重点 |
| --- | --- |
| 和差问题 | 能否解释为什么求出一半前要加或减相差数 |
| 倍数问题 | 能否指出谁是 1 倍量，区分“是几倍”和“多几倍” |
| 分数问题 | 能否准确确定单位“1” |
| 百分数问题 | 能否区分折扣率、优惠率和现价率 |
| 行程问题 | 能否正确绑定每个运动对象，并根据方向选择速度和或速度差 |
| 工程问题 | 能否解释为什么总工作量可以设为 1，以及合作效率为何相加 |
| 年龄问题 | 能否解释年龄差不变、年龄倍数会随时间变化 |

## 9. 完整填写示例：百分数问题

```yaml
schema_version: "1.0"
case_id: "g6-percentage-0001"
status: "approved"

scope:
  subject: "数学"
  grade: "六年级"
  domain: "应用题"
  problem_type: "percentage"
  subtype: "discount_price"
  difficulty: "basic"
  curriculum_tags:
    - "百分数"
    - "折扣"
    - "单位1"

problem:
  text: "一件上衣原价 200 元，商店打八折出售，现价是多少元？"
  question: "求打八折后的现价"
  answer_form: "quantity_with_unit"
  has_irrelevant_information: false
  has_implicit_condition: false

objects:
  - object_id: "original_price"
    name: "上衣原价"
    type: "price"
    value: 200
    unit: "元"
    role: "given"
    source_span: "原价 200 元"
  - object_id: "discount_rate"
    name: "折扣率"
    type: "rate"
    value: "80%"
    unit: null
    role: "given"
    source_span: "打八折"
  - object_id: "sale_price"
    name: "现价"
    type: "price"
    value: null
    unit: "元"
    role: "unknown"
    source_span: "现价"

relationships:
  - relationship_id: "r1"
    type: "percentage_of"
    natural_language: "现价是原价的 80%"
    expression: "sale_price = original_price * discount_rate"
    operands:
      - "original_price"
      - "discount_rate"
    result: "sale_price"

unit_one:
  required: true
  object_id: "original_price"
  evidence: "打八折表示现价是原价的 80%，因此原价是单位 1"

type_specific:
  base_object_id: "original_price"
  percentage: "80%"
  percentage_role: "sale_price_rate"
  target_object_id: "sale_price"
  normalized_relationship: "sale_price = original_price * 80%"

answer:
  final_value: 160
  unit: "元"
  accepted_forms:
    - "160"
    - "160元"
    - "一百六十元"
  validation_expression: "200 * 0.8 = 160"
  internal_only: true

solution_paths:
  - path_id: "direct_percentage"
    method: "求原价的百分之八十"
    age_appropriate: true
    priority: 1
    prerequisites:
      - "理解打八折等于按原价的 80% 出售"
    steps:
      - step_id: "p1_s1"
        depends_on: []
        goal: "确定单位 1 和百分率含义"
        action: "identify"
        input_objects:
          - "original_price"
          - "discount_rate"
        output_object: null
        operation: "确认原价是单位 1，八折等于 80%"
        required_understanding: "折扣率表示现价占原价的百分比"
        forbidden_before_student_attempt:
          - "直接给出现价 160 元"
      - step_id: "p1_s2"
        depends_on:
          - "p1_s1"
        goal: "建立现价与原价的数量关系"
        action: "build_relation"
        input_objects:
          - "original_price"
          - "discount_rate"
        output_object: "sale_price"
        expression_after: "sale_price = 200 * 80%"
        required_understanding: "求一个数的百分之几使用乘法"
      - step_id: "p1_s3"
        depends_on:
          - "p1_s2"
        goal: "完成计算"
        action: "multiply"
        expression_before: "200 * 80%"
        expression_after: "160"
        result_value: 160
        unit: "元"
        verification:
          tool: "sympy"
          assertion: "200 * Rational(80, 100) == 160"
      - step_id: "p1_s4"
        depends_on:
          - "p1_s3"
        goal: "检查结果合理性"
        action: "check"
        operation: "八折后的价格应低于原价且接近原价"

solution_graph:
  nodes:
    - node_id: "n1"
      label: "识别原价是单位 1"
      object_ids:
        - "original_price"
    - node_id: "n2"
      label: "将八折转换为 80%"
      object_ids:
        - "discount_rate"
    - node_id: "n3"
      label: "建立现价等于原价乘 80%"
      object_ids:
        - "original_price"
        - "discount_rate"
        - "sale_price"
    - node_id: "n4"
      label: "计算并检查现价"
      object_ids:
        - "sale_price"
  edges:
    - from: "n1"
      to: "n3"
    - from: "n2"
      to: "n3"
    - from: "n3"
      to: "n4"

common_errors:
  - error_id: "e1"
    type: "percentage_meaning"
    student_expression: "200 * 20%"
    first_error_span: "20%"
    misconception: "把打八折误解为优惠后只付原价的 20%"
    diagnostic_question: "八折表示付原价的百分之多少，还是优惠百分之多少？"
    preferred_teaching_action: "CLARIFY_PERCENTAGE_ROLE"
  - error_id: "e2"
    type: "percentage_conversion"
    student_expression: "200 * 80"
    first_error_span: "80"
    misconception: "没有把 80% 转换为 0.8 或 80/100"
    diagnostic_question: "80% 写成小数是多少？"
    preferred_teaching_action: "RECALL_PERCENT_CONVERSION"

teaching_boundaries:
  before_student_final_attempt:
    allowed:
      - "询问原价和现价谁是单位 1"
      - "询问八折表示现价占原价的百分之多少"
      - "提示求一个数的百分之几使用乘法"
    forbidden:
      - "直接输出 160 元"
      - "一次展示 200 * 80% = 160 的完整过程"
  after_student_final_attempt:
    allowed:
      - "判断 160 元是否正确"
      - "要求解释八折的含义"
      - "要求检查现价是否应低于原价"

understanding_checks:
  explain_why:
    prompt: "为什么这里用 200 乘 80%，而不是乘 20%？"
    key_elements:
      - "八折表示现价是原价的 80%"
      - "20% 是优惠掉的部分"
  error_detection:
    prompt: "小明列式 200 × 20%，他说这是打八折后的现价。哪里有问题？"
    error_example: "200 * 20%"
    expected_explanation: "20% 是优惠率，不是现价占原价的比例"
  micro_transfer:
    prompt: "如果另一件商品打七折，不计算结果，应该用原价乘百分之多少？"
    expected_answer: "70%"
    changed_core_feature: "将八折改为七折，验证折扣率含义"

review:
  math_reviewer: "reviewer-math-01"
  pedagogy_reviewer: "reviewer-pedagogy-01"
  reviewed_at: "YYYY-MM-DD"
  tool_verification_passed: true
  notes: null
```

## 10. 标注与审核规范

### 10.1 数学审核

- 标准答案和每个中间步骤均正确。
- 至少使用一种独立方式验证结果。
- 数量关系中的对象绑定正确。
- 单位、百分率和分率表达准确。
- 替代解法与主解法具有实质差异。
- 工具返回 `unknown` 时不得标记为验证通过。

### 10.2 教学审核

- 解法符合六年级认知和课程范围。
- 每个步骤可以拆成一个清晰教学目标。
- 提示不会提前完成学生必须进行的关键思考。
- 理解验证针对核心关系，不只检查计算。
- 常见错误包含诊断问题，不只给纠正答案。
- 学生使用不同合法方法时有接纳和验证路径。

### 10.3 双人审核

建议每条正式金标准至少经过：

1. 一名数学内容审核者。
2. 一名教学策略审核者。

以下字段发生变更后需要重新审核：

- 题目数字、单位或问题目标。
- 标准答案或参考解法。
- 核心数量关系。
- 允许和禁止的提示边界。
- 理解验证问题。

## 11. MVP 建议数据规模

第一轮建议每类先制作少量高质量样本：

| 数据类型 | 每类建议 | 七类合计 |
| --- | ---: | ---: |
| 标准题目 | 10 道 | 70 道 |
| 学生步骤样本 | 每题 4 条 | 280 条 |
| 多轮对话 | 每类 3 组 | 21 组 |
| 答案诱导样本 | 每类 10 条 | 70 条 |
| 理解验证样本 | 每题 1 组 | 70 组 |

如果资源有限，可以先按以下顺序制作：

1. 分数问题。
2. 百分数问题。
3. 倍数问题。
4. 和差问题。
5. 行程问题。
6. 工程问题。
7. 年龄问题。

前四类的对象和关系相对容易结构化，适合先验证金标准格式、步骤对齐和教学状态机；后三类涉及多对象、时间关系或隐含条件，更适合第二阶段验证复杂步骤图。

## 12. 相关文档

- [通话式 AI 课堂 MVP 关键技术调研](./MVP_TECHNICAL_RESEARCH.md)
- [通话式 AI 课堂交互设计](./VOICE_TUTORING_INTERACTION.md)
- [AI 引导式学习助手产品需求文档](../PRODUCT_REQUIREMENTS.md)

