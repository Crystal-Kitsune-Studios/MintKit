"""PiSugar 3 power reader for MintKit.

Stdlib only, no smbus, no pip installs, and it never raises. Returns the same
shape as ``launcher.battery.get()`` so the two are interchangeable::

    {"pct": int, "charging": bool}   or   None when the power state is unknown

``None`` is important and is not the same as "on battery". Callers must treat
unknown as "behave exactly as before", never as a licence to change policy.

Three sources, tried cheapest-first:

1. ``pisugar-server``, over its unix socket or TCP 8423, if the daemon runs.
   This is the documented public API and is preferred, because the daemon
   already owns the bus and smooths the readings.
2. Direct I2C on ``/dev/i2c-1``, address ``0x57``, via ioctl. No third party
   library needed.
3. Nothing available, return ``None``.

Register map, from the official PiSugar 3 I2C datasheet:

===========  =========================================================
0x02 bit 7   external power connected, 1 means plugged in
0x2A         calculated battery percentage
0x22 / 0x23  battery voltage, high byte then low byte, in mV
===========  =========================================================

Override the bus or address with the ``MINTKIT_PISUGAR_BUS`` and
``MINTKIT_PISUGAR_ADDR`` environment variables if you ever remap them.
"""

import os
import socket

# ---------------------------------------------------------------------------
# Hardware constants
# ---------------------------------------------------------------------------
I2C_BUS = os.environ.get("MINTKIT_PISUGAR_BUS", "1")
I2C_ADDR = int(os.environ.get("MINTKIT_PISUGAR_ADDR", "0x57"), 0)
I2C_SLAVE = 0x0703          # linux/i2c-dev.h

REG_CTRL = 0x02             # bit 7: external power connected
REG_PCT = 0x2A              # battery percentage
REG_VOLT_H = 0x22
REG_VOLT_L = 0x23
BIT_POWER_PLUGGED = 1 << 7

SOCK_PATH = "/tmp/pisugar-server.sock"
TCP_ADDR = ("127.0.0.1", 8423)
TIMEOUT = 0.4               # generous for localhost, still bounded


# ---------------------------------------------------------------------------
# Source 1: pisugar-server
# ---------------------------------------------------------------------------
def _ask(sock, cmd):
    """Send one command, return the value after the colon, or None."""
    sock.sendall((cmd + "\n").encode("ascii"))
    reply = sock.recv(256).decode("ascii", "replace").strip()
    if ":" not in reply:
        return None
    return reply.split(":", 1)[1].strip()


def _connect():
    """Unix socket first, then TCP. Returns a connected socket or None."""
    if hasattr(socket, "AF_UNIX") and os.path.exists(SOCK_PATH):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(TIMEOUT)
            s.connect(SOCK_PATH)
            return s
        except Exception:
            pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT)
        s.connect(TCP_ADDR)
        return s
    except Exception:
        return None


def from_server():
    """Read via pisugar-server. Returns a dict or None."""
    try:
        s = _connect()
    except Exception:
        return None
    if s is None:
        return None
    try:
        pct = _ask(s, "get battery")
        if pct is None:
            return None
        # battery_power_plugged is the accurate one on the new models. Fall
        # back to battery_charging on older firmware that lacks it.
        plugged = _ask(s, "get battery_power_plugged")
        if plugged is None or plugged.lower() not in ("true", "false"):
            plugged = _ask(s, "get battery_charging")
        if plugged is None or plugged.lower() not in ("true", "false"):
            return None
        return {"pct": int(round(float(pct))),
                "charging": plugged.lower() == "true"}
    except Exception:
        return None
    finally:
        try:
            s.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Source 2: direct I2C
# ---------------------------------------------------------------------------
def _read_regs(regs):
    """Read a list of single byte registers in one open. None on any failure."""
    fd = None
    try:
        import fcntl                  # linux only, and it can fail. inside try.
        path = "/dev/i2c-" + str(I2C_BUS)
        if not os.path.exists(path):
            return None
        fd = os.open(path, os.O_RDWR)
        fcntl.ioctl(fd, I2C_SLAVE, I2C_ADDR)
        out = []
        for reg in regs:
            os.write(fd, bytes([reg]))
            data = os.read(fd, 1)
            if not data:
                return None
            out.append(data[0])
        return out
    except Exception:
        return None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass


def from_i2c():
    """Read straight off the bus. Returns a dict or None."""
    try:
        vals = _read_regs([REG_CTRL, REG_PCT])
    except Exception:
        return None
    if not vals or len(vals) != 2:
        return None
    ctrl, pct = vals
    if not 0 <= pct <= 100:
        return None                   # nonsense, treat the bus as unreadable
    return {"pct": int(pct),
            "charging": bool(ctrl & BIT_POWER_PLUGGED)}


def voltage():
    """Battery voltage in volts, or None. Diagnostics only."""
    try:
        vals = _read_regs([REG_VOLT_H, REG_VOLT_L])
    except Exception:
        return None
    if not vals or len(vals) != 2:
        return None
    mv = (vals[0] << 8) | vals[1]
    if not 2000 <= mv <= 5000:
        return None
    return mv / 1000.0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def read():
    """``{"pct": int, "charging": bool}`` or ``None``. Never raises."""
    for source in (from_server, from_i2c):
        try:
            info = source()
        except Exception:
            info = None
        if isinstance(info, dict) and "pct" in info and "charging" in info:
            return info
    return None


# Alias, so this module is a drop in for launcher.battery in a pinch.
get = read


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
def diagnose():
    """Print exactly why a read failed.

    Everything above deliberately swallows errors, because a screen saver that
    raises takes the launcher down. That is correct at runtime and useless
    when debugging, so this one prints the real exception instead.
    """
    try:
        import stat as _stat
        path = "/dev/i2c-" + str(I2C_BUS)
        print("bus      :", path,
              "present" if os.path.exists(path) else "MISSING")

        if os.path.exists(path):
            st = os.stat(path)
            owner, group = str(st.st_uid), str(st.st_gid)
            try:
                import grp
                import pwd
                owner = pwd.getpwuid(st.st_uid).pw_name
                group = grp.getgrgid(st.st_gid).gr_name
            except Exception:
                pass
            print("mode     :", _stat.filemode(st.st_mode), owner, group)
            print("access   : read", os.access(path, os.R_OK),
                  "write", os.access(path, os.W_OK))

        try:
            import grp
            names = sorted(grp.getgrgid(g).gr_name for g in os.getgroups())
        except Exception:
            names = os.getgroups()
        print("me       : uid", os.geteuid(), "groups", names)

        print("daemon   :", "socket present" if os.path.exists(SOCK_PATH)
              else "no socket at " + SOCK_PATH)

        try:
            import fcntl
        except Exception as exc:
            print("fcntl    : UNAVAILABLE", exc)
            return

        # 0x57 is the PiSugar MCU, 0x68 is its RTC. Seeing either proves the
        # pogo pins are making contact.
        for addr in (I2C_ADDR, 0x68):
            fd = None
            try:
                fd = os.open(path, os.O_RDWR)
                fcntl.ioctl(fd, I2C_SLAVE, addr)
                os.write(fd, bytes([0x00]))
                data = os.read(fd, 1)
                print(f"addr 0x{addr:02x}: responded 0x{data[0]:02x}")
            except Exception as exc:
                print(f"addr 0x{addr:02x}: {type(exc).__name__}: {exc}")
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except Exception:
                        pass

        for name, reg in (("ctrl 0x02", REG_CTRL), ("pct  0x2a", REG_PCT),
                          ("volt 0x22", REG_VOLT_H), ("volt 0x23", REG_VOLT_L)):
            fd = None
            try:
                fd = os.open(path, os.O_RDWR)
                fcntl.ioctl(fd, I2C_SLAVE, I2C_ADDR)
                os.write(fd, bytes([reg]))
                data = os.read(fd, 1)
                print(f"{name}: 0x{data[0]:02x} ({data[0]})")
            except Exception as exc:
                print(f"{name}: {type(exc).__name__}: {exc}")
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
    except Exception as exc:
        print("diagnose itself failed:", type(exc).__name__, exc)


def scan():
    """Probe every valid 7 bit address and report anything that answers.

    Errno 121 at one address only says that address stayed silent. This says
    whether the bus is populated at all, which is the difference between a
    wiring or contact fault and a wrong address.
    """
    path = "/dev/i2c-" + str(I2C_BUS)
    print("scanning", path)
    try:
        import fcntl
    except Exception as exc:
        print("fcntl unavailable:", exc)
        return

    found = []
    errors = {}
    for addr in range(0x03, 0x78):
        fd = None
        try:
            fd = os.open(path, os.O_RDWR)
            fcntl.ioctl(fd, I2C_SLAVE, addr)
            os.read(fd, 1)
            found.append(addr)
        except OSError as exc:
            errors[exc.errno] = errors.get(exc.errno, 0) + 1
        except Exception as exc:
            print("unexpected:", type(exc).__name__, exc)
            return
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass

    if found:
        print("responded:", " ".join(f"0x{a:02x}" for a in found))
        if I2C_ADDR in found:
            print("the PiSugar is present at 0x%02x" % I2C_ADDR)
        else:
            print("no answer at 0x%02x, so the device is not where we "
                  "expected" % I2C_ADDR)
    else:
        print("nothing responded on any address")
        print("the bus works, so this is physical: no device is connected,")
        print("the pogo pins are not making contact, or it is unpowered")
    print("errno tally:", {k: v for k, v in sorted(errors.items())})


if __name__ == "__main__":
    import sys
    if "--scan" in sys.argv:
        scan()
        raise SystemExit(0)
    print("server :", from_server())
    print("i2c    :", from_i2c())
    print("voltage:", voltage())
    result = read()
    print("read   :", result)
    if result is None:
        print()
        diagnose()
