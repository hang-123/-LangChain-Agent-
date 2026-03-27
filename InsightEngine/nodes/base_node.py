# InsightEngineLC/nodes/base_node.py
from abc import ABC, abstractmethod
from InsightEngine.state.state import InsightState


class BaseNode(ABC):
    """
    所有节点的基类，和原项目的 base_node 角色相同：统一接口/日志。
    """

    name: str = "base_node"

    @abstractmethod
    def run(self, state: InsightState) -> InsightState:
        ...

    def __call__(self, state: InsightState) -> InsightState:
        print(f"[NODE] 开始执行：{self.name}")
        new_state = self.run(state)
        print(f"[NODE] 结束执行：{self.name}")
        return new_state
