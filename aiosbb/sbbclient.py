__all__ = "SBBClient"

from asyncio import (
    Semaphore,
    StreamReader,
    StreamWriter,
    TimeoutError,
    open_connection,
    sleep,
    wait_for,
)
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any, Callable, Optional, Tuple, Union

from .patterns import ipv4_pattern
from .validations import Validations

log = getLogger()

init_commands = ("configure echoCommands 1", "detatchController")


@dataclass
class SBBClient(Validations):
    ip: str
    timeout: float = 1.0
    verbose: bool = False
    semaphore: Semaphore = field(init=False)
    connected: bool = field(init=False)
    reader: StreamReader = field(init=False)
    writer: StreamWriter = field(init=False)
    log: Callable = field(init=False)

    @staticmethod
    def _validate_ip(ip: str, **_: object) -> Optional[str]:
        if ipv4_pattern.match(ip):
            return ip
        else:
            raise ValueError("ip looks invalid")

    def __post_init__(self) -> None:
        super().__post_init__()
        self.semaphore = Semaphore(1)
        self.connected = False
        self.reader, self.writer = [None] * 2
        if self.verbose:
            self.log = log.info
        else:
            self.log = log.debug

    async def _connect(self) -> None:
        self.reader, self.writer = await open_connection(
            self.ip, port=6000, limit=(1024 * 1024)
        )
        self.connected = True

    async def __call__(self, *args) -> Union[Tuple[Any, ...], bool, Any]:
        res = []
        try:
            if not self.connected:
                self.log(f"[...] connecting to {self.ip}")
                await wait_for(self._connect(), self.timeout)
                self.log(f"[...] setup connection {self.ip}")
                await wait_for(self(*init_commands), self.timeout)
                self.log(f"[ok!] connected to {self.ip}")
            await self.semaphore.acquire()
            self.log("[...] starting transaction")
            for command in args:
                self.log(f"[>>>] sending {command}")
                command += "\r\n"
                self.writer.write(command.encode())
                await wait_for(self.writer.drain(), self.timeout)
                while True:
                    r = await wait_for(self.reader.readline(), self.timeout)
                    if r == command.encode():
                        self.log("[<<<] received command echo")
                        if "Seq" in command:
                            self.log("[...] waiting for Sequence to finish")
                            continue
                        break
                    else:
                        response = r[:-1].decode()
                        self.log(f"[<<<] received response of len {len(response)}")
                        res.append(response)
                        if response == "done":
                            self.log("[ok!] Sequence finished")
                            break
                    await sleep(0)
        except TimeoutError:
            self.connected = False
            log.error("[err] something timed out")
        finally:
            self.semaphore.release()
            self.log(f"[ok!] transaction finished with {len(res)} responses!")
        if res:
            if len(res) == 1:
                return res[0]
            else:
                return tuple(res)
        else:
            return True
