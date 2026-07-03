"""Few-shot 示例模板."""

FEW_SHOT_EXAMPLE = """
## 示例 1：简单任务

用户：今天北京天气怎么样？

Agent 思考：这需要实时数据，我应该搜索。
```json
{"tool": "web_search", "arguments": {"query": "北京天气 今天"}}
"""