---
name: place_normalization
description: 历史地名归一化——将原文地名解析到带时间范围的 historical place instance
version: 1.0.0
---

# 历史地名归一化

## 适用场景

当回答、事件抽取或地图展示涉及历史地名时，使用本方法：

- 同名地名可能跨朝代复用，如“长安”。
- 地名需要绑定地图坐标。
- 事件地点需要与时间线联动。
- 用户问题包含朝代、年号、帝王、政区等上下文。

## 核心原则

1. 保留原文地名，不用现代地名覆盖原文。
2. 优先归一化到 `place_instance_id`，而不是归一化到一个永恒 canonical name。
3. 地名 instance 必须包含起止时间、地理对象类型、现代近似位置和来源。
4. 无法消歧时返回候选和低置信度，不强行选择。

## 输出字段

```yaml
raw_name: 长安
place_instance_id: hrg:tang:changan:618-904
default_spelling: 长安
feature_type: 都城
begin_year: 618
end_year: 904
present_location:
  text: 陕西省西安市
  longitude: 108.94
  latitude: 34.26
confidence: high
source_refs:
  - registry:places/tang_places.yaml#hrg:tang:changan:618-904
```

## 注意事项

- 坐标是现代近似点，不代表古城边界。
- “京师”“西京”等称谓必须结合上下文判断。
- 如果缺少朝代上下文，但事件年份足以过滤候选，可以使用事件年份消歧。
