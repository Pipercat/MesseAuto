#!/usr/bin/env python3
import os
import select
import sys
import termios
import time


BAUD_RATES = {
    115200: termios.B115200,
    9600: termios.B9600,
}


def configure_serial(fd: int, baud: int) -> None:
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = BAUD_RATES.get(baud, termios.B115200)
    attrs[5] = BAUD_RATES.get(baud, termios.B115200)
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-0001"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    configure_serial(fd, baud)

    print(f"Live-Log {port} @ {baud}. Stop mit Ctrl+C.")
    print("Druecke jetzt Buttons/Relais: es erscheinen LOG- und Statuszeilen.")
    buffer = b""

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0.25)
            if not ready:
                continue
            chunk = os.read(fd, 4096)
            if not chunk:
                time.sleep(0.05)
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace").strip()
                log_index = text.find("LOG ")
                json_index = text.find("{")
                if log_index >= 0 and (json_index < 0 or log_index < json_index):
                    print(text[log_index:], flush=True)
                elif json_index >= 0:
                    print(text[json_index:], flush=True)
    except KeyboardInterrupt:
        print("\nLive-Log beendet.")
        return 0
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
