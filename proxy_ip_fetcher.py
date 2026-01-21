import requests
import sys

# Proxy configuration
PROXY_HOST = "us2.cliproxy.io"
PROXY_PORT = 3010
PROXY_USERNAME = "uvoa1123294-region-Rand"
PROXY_PASSWORD = "mpithu35"

# Public IP service
IP_SERVICE_URL = "https://api.ipify.org"

def get_ip_through_proxy():
    """
    Connect to the proxy server and fetch the client's public IPv4 address.
    
    Returns:
        str: The IPv4 address if successful, None otherwise
    """
    # Configure proxy with authentication
    proxies = {
        "http": f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}",
        "https": f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
    }
    
    try:
        # Query ipify through the proxy to get our public IP
        response = requests.get(
            IP_SERVICE_URL,
            proxies=proxies,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; python-requests)"}
        )
        
        if response.status_code == 200:
            ip_address = response.text.strip()
            # Basic IPv4 validation
            if is_valid_ipv4(ip_address):
                return ip_address
            else:
                print(f"Error: Received invalid IP format: {ip_address}", file=sys.stderr)
                return None
        else:
            print(f"Error: IP service returned status code {response.status_code}", file=sys.stderr)
            return None
            
    except requests.exceptions.Timeout:
        print("Error: Connection timeout - unable to reach proxy or IP service", file=sys.stderr)
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Error: Connection failed - unable to connect to proxy or IP service", file=sys.stderr)
        print(f"Details: {str(e)}", file=sys.stderr)
        return None
    except requests.exceptions.ProxyError as e:
        print(f"Error: Proxy connection failed - check proxy credentials and connectivity", file=sys.stderr)
        print(f"Details: {str(e)}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error: Unexpected error occurred", file=sys.stderr)
        print(f"Details: {str(e)}", file=sys.stderr)
        return None

def is_valid_ipv4(ip):
    """
    Basic IPv4 address validation.
    
    Args:
        ip (str): IP address string to validate
        
    Returns:
        bool: True if valid IPv4 format
    """
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    
    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False
        except ValueError:
            return False
    
    return True

def main():
    """Main function to fetch and display IP address"""
    print("Proxy IP Fetcher", file=sys.stderr)
    print("================", file=sys.stderr)
    print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}", file=sys.stderr)
    print(f"Service: {IP_SERVICE_URL}", file=sys.stderr)
    print("Connecting...", file=sys.stderr)
    
    ip_address = get_ip_through_proxy()
    
    if ip_address:
        # Clean output - just the IP address to stdout
        print(ip_address)
        print(f"\nSuccess! Your public IPv4 address is: {ip_address}", file=sys.stderr)
        return 0
    else:
        print(f"\nFailed to retrieve IP address", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
