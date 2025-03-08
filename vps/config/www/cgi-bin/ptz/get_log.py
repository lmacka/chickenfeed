#!/usr/bin/env python3
# Script to retrieve the PTZ log file
# Returns plain text content of the log file

import os
import sys

def main():
    """Main CGI function"""
    # Print HTTP headers
    print("Content-Type: text/plain")
    print("")
    
    log_file = '/config/www/cgi-bin/ptz/ptz_log.txt'
    
    try:
        if os.path.exists(log_file):
            # Get the last 100 lines of the log
            with open(log_file, 'r') as f:
                lines = f.readlines()
                lines = lines[-100:] if len(lines) > 100 else lines
                print(''.join(lines))
        else:
            print("Log file does not exist yet. No PTZ commands have been executed.")
    except Exception as e:
        print(f"Error reading log file: {str(e)}")

if __name__ == "__main__":
    main() 