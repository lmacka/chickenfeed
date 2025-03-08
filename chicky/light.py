import automationhat
import sys

def relay_on():
    # Turn on relay 1
    automationhat.relay.one.on()
    print("Relay 1 ON")

def relay_off():
    # Turn off relay 1
    automationhat.relay.one.off()
    print("Relay 1 OFF")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 light.py <on|off>")
        sys.exit(1)

    state = sys.argv[1].lower()

    if state == "on":
        relay_on()
    elif state == "off":
        relay_off()
    else:
        print("Invalid argument. Use 'on' or 'off'.")
        sys.exit(1)