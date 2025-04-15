import nmap
import socket
import netifaces
from urllib.request import urlopen, Request
import json

class Camera:
    """
    A class to represent a camera device.
    It provides methods to check the connection, control the camera,
    and retrieve camera configurations.
    """
    def __init__(self, ip):
        """
        Initialize the camera with the given IP address.
            :param ip: IP address of the camera
        """
        if not ip:
            raise ValueError("IP address is required")
        self.ip = ip
        self.url = "http://" + ip


    def get_http_request(self, url):
        """
        Create an HTTP request to the camera.
            :param url: URL of the camera
            :return: HTTP request object
        """
        httprequest = Request(url, method='GET')
        httprequest.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')
        httprequest.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
        return httprequest

    def cek_camera_esp_ai_thinker(self):
        """
        Check the connection to the ESP AI Thinker camera.
            :param ip: IP address of the camera
            :return: Response from the camera
        """
        full_url = self.url + "/status"
        httprequest = self.get_http_request(full_url)

        with urlopen(httprequest) as response:
            if response.status != 200:
                raise Exception(f"Failed to connect to camera: {response.status}")
        return True

    def cek_camera_configuration(self):
        """
        Check the camera configuration.
            :param ip: IP address of the camera
            :return: Response from the camera configuration command
        """
        full_url = self.url + "/status"
        httprequest = self.get_http_request(full_url)
        data = None
        with urlopen(httprequest) as response:
            if response.status != 200:
                raise Exception(f"Failed to get camera configuration: {response.status}")
            response_data = response.read().decode()
            try:
                data = json.loads(response_data)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse camera configuration: {e}")
        return data
    
    def set_camera_xclk(self, xclk:int):
        """
        Set the camera XCLK value.
            :param ip: IP address of the camera
            :return: Response from the camera XCLK command
        """
        try:
            full_url = self.url + "/xclk?xclk=" + str(xclk)
            httprequest = self.get_http_request(full_url)
            with urlopen(httprequest) as response:
                if response.status != 200:
                    return False
        except Exception as e:
            print(full_url)
            print(f"Error setting camera XCLK: {e}")
        return True
    
    def set_camera_resolution(self, resolution:int):
        """
        Set the camera resolution.
            :param ip: IP address of the camera
            :return: Response from the camera resolution command
        """
        full_url = self.url + "/control?var=framesize&val=" + str(resolution)
        httprequest = self.get_http_request(full_url)
        with urlopen(httprequest) as response:
            if response.status != 200:
                return False
        return True

def scan_camera(ip:str):
    """
    scans the local network for cameras based on the provided IP address.
    It uses the nmap library to perform a network scan and identifies devices
    with open ports commonly used for camera streaming.
    Args:
        ip (str): The IP address of the device to scan.
    Returns:
        list[dict]: A list of dictionaries, where each dictionary contains the following keys:
            - 'ip' (str): The IP address of the device.
            - 'hostname' (str): The hostname of the device (or 'Unknown' if not resolvable).
            - 'ports' (list[int]): A list of open ports on the device.
            - 'vendor' (str): The vendor information of the device (if available).
    """
    network_range = f"{ip.rsplit('.', 1)[0]}.0/24"
    cameras = scan_network(network_range)
    if not cameras:
        return None
    return cameras

def scan_network(network_range):
    """
    Scans a given network range for devices with open camera streaming ports.
    This function utilizes the nmap library to scan the specified network range
    for devices with open ports commonly used for camera streaming. It returns
    a list of possible cameras with their IP addresses, hostnames, open ports,
    and vendor information.
    Args:
        network_range (str): The network range to scan, specified in CIDR notation
                             (e.g., "192.168.1.0/24").
    Returns:
        list[dict]: A list of dictionaries, where each dictionary contains the following keys:
            - 'ip' (str): The IP address of the device.
            - 'hostname' (str): The hostname of the device (or 'Unknown' if not resolvable).
            - 'ports' (list[int]): A list of open ports on the device.
            - 'vendor' (str): The vendor information of the device (if available).
    Raises:
        nmap.PortScannerError: If there is an issue with the nmap installation or execution.
        socket.herror: If there is an error resolving the hostname of a device.
    Example:
        >>> scan_network("192.168.1.0/24")
        [
            {
                'ip': '192.168.1.10',
                'hostname': 'camera1.local',
                'ports': [81],
                'vendor': 'SomeVendor'
            },
            {
                'ip': '192.168.1.15',
                'hostname': 'Unknown',
                'ports': [81],
        ]
    """
    # Inisialisasi pemindai nmap
    nm = nmap.PortScanner()

    # Port streaming kamera
    camera_ports = "81"  # stream
    
    print(f"Memindai jaringan: {network_range} untuk port: {camera_ports}...")
    
    # Lakukan pemindaian
    nm.scan(hosts=network_range, arguments=f'-p {camera_ports} --open')
    
    # Simpan hasil kamera yang mungkin
    possible_cameras = []
    
    # Iterasi hasil pemindaian
    for host in nm.all_hosts():
        host_info = {
            'ip': host,
            'hostname': '',
            'ports': [],
            'vendor': ''
        }
        try:
            host_info['hostname'] = socket.gethostbyaddr(host)[0]
        except socket.herror:
            host_info['hostname'] = 'Unknown'
        
        # Cek port yang terbuka
        for proto in nm[host].all_protocols():
            lport = nm[host][proto].keys()
            for port in lport:
                host_info['ports'].append(port)
        
        # Tambahkan ke daftar jika ada port terbuka yang relevan
        if host_info['ports']:
            possible_cameras.append(host_info)
    
    return possible_cameras

def get_wifi_ip():
    """
    Retrieves the IP address of the Wi-Fi network interface.
    This function iterates through all network interfaces on the system
    and checks for IPv4 addresses. It excludes loopback addresses (127.*)
    and private network addresses starting with 172.*.
    Returns:
        str: The IP address of the Wi-Fi network interface if found.
             Returns "Tidak ditemukan IP Wi-Fi" if no suitable IP is found.
             Returns an error message if an exception occurs.
    """
    try:
        # Dapatkan semua antarmuka jaringan
        interfaces = netifaces.interfaces()
        
        for iface in interfaces:
            # Dapatkan detail antarmuka
            addrs = netifaces.ifaddresses(iface)
            
            # Cek apakah antarmuka punya alamat IPv4
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr['addr']
                    if not ip.startswith('127') and not ip.startswith('172'):
                        return ip
        return "Tidak ditemukan IP Wi-Fi"
    except Exception as e:
        return f"Gagal mendapatkan IP: {e}"
    
if __name__ == "__main__":
    # Contoh penggunaan
    wifi_ip = get_wifi_ip()
    print(f"IP Wi-Fi: {wifi_ip}")
    
    # Tentukan rentang jaringan berdasarkan IP Wi-Fi
    network_range = f"{wifi_ip.rsplit('.', 1)[0]}.0/24"
    print(f"Rentang jaringan: {network_range}")
    cameras = scan_network(network_range)
    
    if cameras:
        print("Kamera yang ditemukan:")
        for camera in cameras:
            print(f"IP: {camera['ip']}, Hostname: {camera['hostname']}, Ports: {camera['ports']}")
    else:
        print("Tidak ada kamera ditemukan.")