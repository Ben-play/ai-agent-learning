"""Bounded parent/child JSONL transport, not an HTTP server or a background queue."""

import argparse
import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Thread

HERE = Path(__file__).resolve().parent


class StartupRefused(RuntimeError):
    pass


class Worker:
    """Start and join exactly one lab child per context. No shell and no network."""

    def __init__(self, directory, *, build="v1", profile="support", outage=False):
        self._args = [sys.executable, "-I", "-B", "-X", "utf8", str(Path(__file__).resolve()),
                      str(directory), "--build", build, "--profile", profile]
        if outage:
            self._args.append("--outage")
        self._process = None
        self.pid = None

    def __enter__(self):
        self._process = subprocess.Popen(self._args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         text=True, encoding="utf-8", bufsize=1)
        self.pid = self._process.pid
        self._lines = Queue()
        self._reader = Thread(target=self._collect, args=(self._process.stdout, self._lines), daemon=True)
        self._reader.start()
        try:
            ready = self._receive()
            if ready != {"status": "ready"}:
                raise StartupRefused(ready["status"])
        except BaseException:
            self.close()
            raise
        return self

    @staticmethod
    def _collect(stream, output):
        try:
            for line in stream:
                output.put(line)
        finally:
            output.put(None)

    def _receive(self):
        try:
            line = self._lines.get(timeout=8)
        except Empty as exc:
            raise RuntimeError("lab worker did not respond in time") from exc
        if line is None:
            raise RuntimeError("lab worker exited before replying")
        return json.loads(line)

    def call(self, operation, **payload):
        if self._process is None or self._process.poll() is not None:
            raise RuntimeError("lab worker is not running")
        message = json.dumps({"operation": operation, "payload": payload}, ensure_ascii=True)
        try:
            self._process.stdin.write(message + "\n")
            self._process.stdin.flush()
            return self._receive()
        except (OSError, RuntimeError, ValueError):
            # A missing response is an unknown outcome. Never reuse this pipe or retry automatically.
            self.close()
            raise

    def close(self):
        if (process := self._process) is None:
            return
        self._process = None
        timed_out = False
        try:
            process.stdin.close()  # EOF exits the child loop; wait for it before opening another writer.
        except BrokenPipeError:
            pass
        finally:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                process.wait(timeout=8)
            finally:
                self._reader.join(timeout=8)
                process.stdout.close()
        if timed_out or process.returncode != 0:
            raise RuntimeError("lab worker did not exit cleanly")

    def __exit__(self, exc_type, exc, tb):
        self.close()


def main():
    sys.path.insert(0, str(HERE))  # Only this checked-in course directory, under isolated mode.
    from host import Host, IncompatibleSchema, PROFILES

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--build", choices=("v1", "v2"), required=True)
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    parser.add_argument("--outage", action="store_true")
    args = parser.parse_args()
    try:
        lab = Host(args.directory, build=args.build, outage=args.outage)
    except IncompatibleSchema:
        print('{"status":"incompatible_schema"}', flush=True)
        return
    print('{"status":"ready"}', flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        result = lab.dispatch(args.profile, request["operation"], request["payload"], fixtures=True)
        print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
