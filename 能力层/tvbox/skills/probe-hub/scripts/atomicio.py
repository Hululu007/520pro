#!/usr/bin/env python3
"""原子写 + 内容不变不重写（S231 L1603-1624 通道层移植）。

原文 `_write_config_file` 只做两件事，但两件都值得抄：

  ① **内容没变就直接返回，不碰文件**——mtime 不变，下游不会误判「有新版本要重跑」，
     git 也不会因为「写了一遍但内容一样」而脏一格；
  ② 变了才 tmp → flush → **fsync** → `os.replace`，半截写不可能落盘。

第 ② 条本仓已有实现（`通用层/skills/space-hub/scripts/space_hub.py` 的 `_atomic_write`），
第 ① 条全仓都没有——space-hub 那件只保证「不会写坏」，不保证「没变就不写」。
技能必须自包含（各自分发、不跨层 import），故此件在 probe-hub 内独立实现，
语义与 space-hub 同源——**这是登记过的重复**（M7）：两边改动要同步。

与原文的一处差异（有意）：原文写完不回读，本件默认**写完回读校验**。
`os.replace` 成功只证明换文件成功，不证明内容对（learn.py 踩过：replace 没抛就
当成写成了，实际内容截断）。回读不一致抛异常，不许静默返回成功。
"""

import os
import tempfile

__all__ = ['write_atomic', 'read_bytes']


def read_bytes(path):
    """读不到返回 None（与「读到了空文件」区分：空文件是 b''）。"""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except FileNotFoundError:
        return None


def write_atomic(path, data, *, binary=False, skip_if_same=True, verify=True):
    """原子写文件。返回 'same'（内容相同未写）或 'written'（真写了）。

    path          目标路径；父目录不存在会自动建
    data          str（按 utf-8 编码）或 bytes（binary=True 时）
    skip_if_same  内容与盘上完全一致就跳过——不碰 mtime、不换 inode
    verify        写完回读比对，不一致抛 IOError（默认开，见模块 docstring）

    失败一律抛异常，不返回 False——「没写成功」和「写成功但内容是空的」必须能被上层
    区分开，用返回值折叠成 bool 就分不清了。
    """
    if not binary and isinstance(data, str):
        raw = data.encode('utf-8')
    else:
        raw = bytes(data)

    if skip_if_same and read_bytes(path) == raw:
        return 'same'

    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.tmp_', dir=d)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())     # 落盘再换名：断电也只会留旧整份
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)           # 换名失败不许留垃圾（残留 tmp 会被误当产物）
        except OSError:
            pass
        raise

    if verify:
        got = read_bytes(path)
        if got != raw:
            raise IOError('写完回读不一致：%s（期望 %d 字节，实得 %d）'
                          % (path, len(raw), len(got) if got is not None else -1))
    return 'written'


def _selftest():
    import shutil
    import time

    fails = []

    def chk(name, cond, detail=''):
        print(f'[{"OK " if cond else "FAIL"}] {name}' + ('' if cond else f'  {detail}'))
        if not cond:
            fails.append(name)

    base = tempfile.mkdtemp(prefix='atomicio_')
    try:
        p = os.path.join(base, 'sub', 'cfg.json')

        # 正：新文件（父目录不存在）→ written 且内容对
        r = write_atomic(p, '{"a":1}')
        chk('新文件写入返回 written', r == 'written', r)
        chk('父目录自动创建', os.path.isfile(p))
        chk('内容与写入一致', read_bytes(p) == b'{"a":1}')

        # 正：同内容再写 → same，且 **inode 不变**（比 mtime 更强的证据：文件根本没被换）
        ino1 = os.stat(p).st_ino
        r = write_atomic(p, '{"a":1}')
        chk('同内容返回 same', r == 'same', r)
        chk('同内容不改 inode（证明真没写）', os.stat(p).st_ino == ino1)

        # 正：改内容 → written，inode 变（证明走的是 replace 而非原地覆盖）
        r = write_atomic(p, '{"a":2}')
        chk('改内容返回 written', r == 'written', r)
        chk('改内容换 inode（replace 语义）', os.stat(p).st_ino != ino1)
        chk('改后内容正确', read_bytes(p) == b'{"a":2}')

        # 反：skip_if_same=False 时同内容也必须写（开关真的接上了）
        ino2 = os.stat(p).st_ino
        r = write_atomic(p, '{"a":2}', skip_if_same=False)
        chk('关掉 skip 后同内容也写', r == 'written' and os.stat(p).st_ino != ino2, r)

        # 边界：空文件（None 与 b"" 必须区分）
        p2 = os.path.join(base, 'empty.txt')
        chk('不存在的文件读出 None', read_bytes(p2) is None)
        chk('写空串返回 written', write_atomic(p2, '') == 'written')
        chk('空文件读出 b""（不是 None）', read_bytes(p2) == b'')
        chk('再写空串返回 same', write_atomic(p2, '') == 'same')

        # 反：目标是目录 → 必须抛异常，且不留 tmp 垃圾
        p3 = os.path.join(base, 'adir')
        os.makedirs(p3)
        raised = False
        try:
            write_atomic(p3, 'x')
        except Exception:
            raised = True
        chk('目标是目录时抛异常（不静默失败）', raised)
        leftovers = [f for f in os.listdir(base) if f.startswith('.tmp_')]
        chk('失败后不留 tmp 残留', not leftovers, str(leftovers))

        # 正：binary 模式
        p4 = os.path.join(base, 'b.bin')
        write_atomic(p4, b'\x00\x01\xff', binary=True)
        chk('二进制写入正确', read_bytes(p4) == b'\x00\x01\xff')

        # 正：中文内容 utf-8 往返（quotepath 教训同型：编码链路要真跑一遍）
        p5 = os.path.join(base, '中文名.json')
        write_atomic(p5, '{"标题":"中文"}')
        chk('中文路径与中文内容往返正常', read_bytes(p5) == '{"标题":"中文"}'.encode('utf-8'))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    if fails:
        print(f'✗ atomicio 自检 {len(fails)} 项失败：{fails}')
        return 1
    print('✓ atomicio 自检全部通过（S231 L1603-1624 通道层：原子写 + 内容不变不重写）')
    return 0


if __name__ == '__main__':
    import sys
    if '--selftest' in sys.argv:
        raise SystemExit(_selftest())
    print(__doc__)
    raise SystemExit(2)
