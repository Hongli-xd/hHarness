---
name: time_normalization
description: 历史时间归一化——将年号纪年等表达解析为公元年并保留原始表达
version: 1.0.0
---

# 历史时间归一化

## 适用场景

当回答、事件抽取或时间线展示涉及年号纪年时，使用本方法：

- “元和十五年”“贞观元年”等年号表达。
- 同一年号跨朝代复用，需要消歧。
- 需要将事件放入公元年时间线。

## 核心原则

1. 保留原文时间表达。
2. 公元年是规范字段之一，不替代年号纪年。
3. 年号必须结合朝代、政权、帝王或上下文消歧。
4. 无法消歧时返回候选和低置信度。

## 输出字段

```yaml
raw_time: 元和十五年
normalized_year: 820
dynasty: 唐
reign_title: 元和
reign_year: 15
emperor: 唐宪宗
confidence: high
source_refs:
  - registry:times/tang_reigns.yaml#reign:tang:xianzong:yuanhe
```

## 注意事项

- 第一阶段只处理年级精度，不处理农历月日到公历日的精确换算。
- 同名年号如“元和”必须用朝代或上下文区分东汉与唐。
- `confidence: low` 时不得把候选当作确定事实写入地图或时间线。
