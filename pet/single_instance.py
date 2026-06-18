import os

from .config import INSTANCE_LOCK_FILE

try:
    import msvcrt
except ImportError:
    msvcrt = None


SINGLE_INSTANCE_LOCK = None


def acquire_single_instance_lock():
    global SINGLE_INSTANCE_LOCK
    if msvcrt is None:
        return True
    try:
        handle = INSTANCE_LOCK_FILE.open("a+b")
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii", errors="ignore"))
        handle.flush()
        SINGLE_INSTANCE_LOCK = handle
        return True
    except OSError:
        try:
            handle.close()
        except Exception:
            pass
        return False


def release_single_instance_lock():
    global SINGLE_INSTANCE_LOCK
    handle = SINGLE_INSTANCE_LOCK
    SINGLE_INSTANCE_LOCK = None
    if not handle:
        return
    try:
        handle.seek(0)
        if msvcrt is not None:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    try:
        handle.close()
    except OSError:
        pass
