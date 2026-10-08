from typing import Protocol, TypeVar

CommandT = TypeVar("CommandT", contravariant=True)
ResultT = TypeVar("ResultT", covariant=True)


class Handler(Protocol[CommandT, ResultT]):
    async def execute(self, command: CommandT) -> ResultT:
        ...
