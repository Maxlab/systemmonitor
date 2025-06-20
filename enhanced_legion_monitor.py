#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Legion 5 Pro Monitor v3.0
Combines advanced system monitoring with Legion-specific hardware optimizations
AMD Ryzen 7 5800H + NVIDIA RTX 3070 + NVMe SSD monitoring
"""

import os
import sys
import time
import subprocess
import threading
import json
import datetime
import argparse
import signal
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    import psutil
except ImportError:
    print("Устанавливаю psutil...")
    subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "--user"], check=True)
    import psutil

try:
    from colorama import init, Fore, Back, Style
    init()
except ImportError:
    print("Устанавливаю colorama...")
    subprocess.run([sys.executable, "-m", "pip", "install", "colorama", "--user"], check=True)
    from colorama import init, Fore, Back, Style
    init()

@dataclass
class TempReading:
    name: str
    temp: float
    source: str
    critical: Optional[float] = None

@dataclass
class SystemAlert:
    timestamp: str
    level: str
    component: str
    message: str
    value: float
    threshold: float

class EnhancedLegionMonitor:
    def __init__(self, export_format: str = "json"):
        self.running = True
        self.export_format = export_format
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = f"enhanced_legion_{timestamp}.{export_format}"
        self.alerts = []
        self.data_history = []
        
        # Legion 5 Pro specific thresholds
        self.thresholds = {
            'cpu_temp': 85.0,        # AMD Ryzen 7 5800H
            'gpu_temp': 78.0,        # RTX 3070 Mobile  
            'nvme_temp': 70.0,       # NVMe SSD
            'cpu_usage': 90.0,
            'memory_usage': 85.0,
            'gpu_power': 125.0,      # RTX 3070 Mobile max
            'gpu_utilization': 95.0,
            'disk_usage': 90.0
        }
        
        # Hardware availability detection
        self.gpu_available = self._check_gpu_availability()
        self.temp_sensors = self._discover_temperature_sensors()
        
    def _check_gpu_availability(self) -> bool:
        """Multi-method GPU availability check for Legion 5 Pro"""
        # Method 1: nvidia-smi
        try:
            result = subprocess.run(['nvidia-smi', '-L'], capture_output=True, timeout=3)
            if result.returncode == 0:
                return True
        except:
            pass
        
        # Method 2: NVIDIA driver via /proc
        try:
            with open('/proc/driver/nvidia/version', 'r') as f:
                return True
        except:
            pass
            
        # Method 3: lspci hardware detection
        try:
            result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=3)
            if 'nvidia' in result.stdout.lower():
                return True
        except:
            pass
            
        return False
    
    def _discover_temperature_sensors(self) -> Dict[str, str]:
        """Legion 5 Pro specific temperature sensor discovery"""
        sensors = {}
        
        # AMD CPU (k10temp) - typical hwmon3 on Legion
        cpu_temp_path = '/sys/class/hwmon/hwmon3/temp1_input'
        if os.path.exists(cpu_temp_path):
            sensors['cpu'] = cpu_temp_path
            
        # NVMe SSD sensors - typical hwmon2 on Legion
        for i in range(1, 4):
            nvme_path = f'/sys/class/hwmon/hwmon2/temp{i}_input'
            if os.path.exists(nvme_path):
                sensors[f'nvme_temp{i}'] = nvme_path
                
        return sensors
    
    def get_all_temperatures(self) -> List[TempReading]:
        """Enhanced temperature monitoring with Legion-specific paths"""
        temperatures = []
        
        # AMD CPU temperature (Legion hwmon3)
        try:
            with open('/sys/class/hwmon/hwmon3/temp1_input', 'r') as f:
                cpu_temp = float(f.read().strip()) / 1000.0
                temperatures.append(TempReading('CPU (Tctl)', cpu_temp, 'k10temp'))
        except:
            # Fallback to generic CPU temperature methods
            cpu_temps = self._get_cpu_temps_fallback()
            temperatures.extend(cpu_temps)
            
        # NVMe SSD temperatures with critical thresholds
        nvme_labels = {
            '1': 'NVMe Composite',
            '2': 'NVMe Sensor 1', 
            '3': 'NVMe Sensor 2'
        }
        
        for temp_num in ['1', '2', '3']:
            try:
                temp_path = f'/sys/class/hwmon/hwmon2/temp{temp_num}_input'
                crit_path = f'/sys/class/hwmon/hwmon2/temp{temp_num}_crit'
                
                with open(temp_path, 'r') as f:
                    nvme_temp = float(f.read().strip()) / 1000.0
                
                # Read critical temperature if available
                critical_temp = None
                try:
                    with open(crit_path, 'r') as f:
                        critical_temp = float(f.read().strip()) / 1000.0
                except:
                    critical_temp = self.thresholds['nvme_temp']
                
                label = nvme_labels.get(temp_num, f'NVMe Temp{temp_num}')
                temperatures.append(TempReading(label, nvme_temp, 'nvme', critical_temp))
            except:
                pass
        
        # GPU temperature
        if self.gpu_available:
            try:
                result = subprocess.run([
                    'nvidia-smi', '--query-gpu=temperature.gpu',
                    '--format=csv,noheader,nounits'
                ], capture_output=True, text=True, timeout=3)
                
                if result.returncode == 0:
                    gpu_temp = float(result.stdout.strip())
                    temperatures.append(TempReading('GPU (RTX 3070)', gpu_temp, 'nvidia'))
            except:
                pass
                
        return temperatures
    
    def _get_cpu_temps_fallback(self) -> List[TempReading]:
        """Fallback CPU temperature methods for compatibility"""
        temps = []
        
        # lm-sensors fallback
        try:
            result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Tctl:' in line:
                        temp_str = line.split('+')[1].split('°')[0].strip()
                        temps.append(TempReading('CPU (Tctl)', float(temp_str), 'sensors'))
                    elif 'Tdie:' in line:
                        temp_str = line.split('+')[1].split('°')[0].strip()
                        temps.append(TempReading('CPU (Tdie)', float(temp_str), 'sensors'))
        except:
            pass
            
        # Generic hwmon fallback
        try:
            hwmon_dirs = glob.glob('/sys/class/hwmon/hwmon*/temp*_input')
            for temp_file in hwmon_dirs[:3]:  # Limit to first 3
                try:
                    with open(temp_file, 'r') as f:
                        temp = float(f.read().strip()) / 1000
                        if 30 < temp < 150:
                            hwmon_name = os.path.basename(os.path.dirname(temp_file))
                            file_name = os.path.basename(temp_file)
                            temps.append(TempReading(f'{hwmon_name}_{file_name}', temp, 'hwmon'))
                except:
                    continue
        except:
            pass
            
        return temps if temps else [TempReading('CPU', 0.0, 'unavailable')]

    def _safe_float(self, value, default=0.0):
        """Safe float conversion handling GPU '[Not Supported]' values"""
        try:
            if value == '[Not Supported]' or value == '[N/A]' or value.strip() == '':
                return default
            clean_value = value.replace('W', '').replace('MHz', '').replace('%', '').strip()
            return float(clean_value)
        except (ValueError, AttributeError):
            return default

    def get_gpu_comprehensive_info(self) -> Dict:
        """Enhanced GPU information with Legion-specific status reporting"""
        gpu_info = {
            'available': self.gpu_available,
            'temp': 0, 'power': 0, 'utilization': 0,
            'memory_used': 0, 'memory_total': 0, 'memory_percent': 0,
            'clock_core': 0, 'clock_memory': 0,
            'fan_speed': 0, 'power_limit': 0,
            'throttle_reasons': [], 'driver_version': 'unknown',
            'status': 'unknown'
        }
        
        if not self.gpu_available:
            return gpu_info
            
        # Test nvidia-smi functionality
        try:
            test_result = subprocess.run(['nvidia-smi', '-L'], capture_output=True, timeout=3)
            if test_result.returncode != 0:
                # GPU detected but nvidia-smi fails
                gpu_info['status'] = 'nvidia-smi unavailable (driver mismatch)'
                
                # Try to get driver version from /proc
                try:
                    with open('/proc/driver/nvidia/version', 'r') as f:
                        version_info = f.read().strip()
                        gpu_info['driver_version'] = version_info.split('\n')[0]
                        gpu_info['status'] = 'detected via /proc, nvidia-smi failed'
                except:
                    pass
                    
                return gpu_info
            
            # nvidia-smi working - get full metrics
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total,clocks.current.graphics,clocks.current.memory,fan.speed,power.limit,driver_version',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                values = result.stdout.strip().split(', ')
                if len(values) >= 4:
                    gpu_info.update({
                        'temp': self._safe_float(values[0], 0),
                        'power': self._safe_float(values[1], 0),
                        'utilization': self._safe_float(values[2], 0),
                        'memory_used': self._safe_float(values[3], 0),
                        'memory_total': self._safe_float(values[4], 0) if len(values) > 4 else 0,
                        'clock_core': self._safe_float(values[5], 0) if len(values) > 5 else 0,
                        'clock_memory': self._safe_float(values[6], 0) if len(values) > 6 else 0,
                        'fan_speed': self._safe_float(values[7], 0) if len(values) > 7 else 0,
                        'power_limit': self._safe_float(values[8], 0) if len(values) > 8 else 0,
                        'driver_version': values[9].strip() if len(values) > 9 else 'unknown',
                        'status': 'nvidia-smi working'
                    })
                    
                    # Calculate memory percentage
                    if gpu_info['memory_total'] > 0:
                        gpu_info['memory_percent'] = (gpu_info['memory_used'] / gpu_info['memory_total']) * 100
            
            # Check throttling status
            throttle_result = subprocess.run([
                'nvidia-smi', '--query-gpu=clocks_throttle_reasons.active',
                '--format=csv,noheader'
            ], capture_output=True, text=True, timeout=3)
            
            if throttle_result.returncode == 0:
                throttle_info = throttle_result.stdout.strip()
                if 'Active' in throttle_info:
                    gpu_info['throttle_reasons'] = ['thermal_throttling']
            else:
                gpu_info['status'] = 'nvidia-smi query failed'
                
        except Exception as e:
            gpu_info['status'] = f'nvidia-smi error: {str(e)[:50]}'
            
        return gpu_info

    def get_system_metrics(self) -> Dict:
        """Enhanced system metrics for Legion monitoring"""
        metrics = {
            'cpu_usage': 0,
            'cpu_freq': 0,
            'memory': {'percent': 0, 'used_gb': 0, 'total_gb': 0, 'available_gb': 0},
            'load_average': {'1m': 0, '5m': 0, '15m': 0},
            'uptime_hours': 0,
            'boot_time': '',
            'processes': 0,
            'disk_usage': []
        }
        
        try:
            # CPU metrics
            metrics['cpu_usage'] = psutil.cpu_percent(interval=1)
            
            freq_info = psutil.cpu_freq()
            if freq_info:
                metrics['cpu_freq'] = freq_info.current
            
            # Memory
            memory = psutil.virtual_memory()
            metrics['memory'] = {
                'percent': memory.percent,
                'used_gb': memory.used / (1024**3),
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3)
            }
            
            # Load average
            load_avg = os.getloadavg()
            metrics['load_average'] = {
                '1m': load_avg[0],
                '5m': load_avg[1],
                '15m': load_avg[2]
            }
            
            # Uptime
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
            metrics['boot_time'] = boot_time.strftime('%Y-%m-%d %H:%M:%S')
            uptime = datetime.datetime.now() - boot_time
            metrics['uptime_hours'] = uptime.total_seconds() / 3600
            
            # Process count
            metrics['processes'] = len(psutil.pids())
            
            # Disk usage (filter out snap packages)
            disk_usage = []
            for partition in psutil.disk_partitions():
                # Skip snap packages and temporary filesystems
                if ('/snap/' in partition.mountpoint or 
                    partition.device.startswith('/dev/loop') or
                    partition.fstype in ['squashfs', 'tmpfs']):
                    continue
                    
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'percent': (usage.used / usage.total) * 100,
                        'used_gb': usage.used / (1024**3),
                        'total_gb': usage.total / (1024**3)
                    })
                except:
                    continue
                    
            metrics['disk_usage'] = disk_usage
            
        except Exception as e:
            pass
            
        return metrics

    def get_battery_info(self) -> Dict:
        """Enhanced battery monitoring for Legion 5 Pro"""
        battery_info = {
            'present': False,
            'percent': 0,
            'charging': False,
            'voltage': 0,
            'power_source': 'Unknown'
        }
        
        try:
            # Battery info via psutil
            battery = psutil.sensors_battery()
            if battery:
                battery_info.update({
                    'present': True,
                    'percent': battery.percent,
                    'charging': battery.power_plugged,
                    'power_source': 'AC' if battery.power_plugged else 'Battery'
                })
            
            # Legion battery voltage from hwmon1
            try:
                with open('/sys/class/hwmon/hwmon1/in0_input', 'r') as f:
                    voltage_raw = float(f.read().strip())
                    battery_info['voltage'] = voltage_raw / 1000000  # Convert to volts
            except:
                pass
                
        except Exception as e:
            pass
            
        return battery_info

    def get_system_errors_detailed(self) -> List[Dict]:
        """Detailed system error analysis"""
        errors = []
        
        try:
            # Critical errors from journalctl
            result = subprocess.run([
                'journalctl', '-p', 'err', '-n', '5', '--no-pager', '--output=json'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            log_entry = json.loads(line)
                            error_info = {
                                'timestamp': log_entry.get('__REALTIME_TIMESTAMP', ''),
                                'message': log_entry.get('MESSAGE', ''),
                                'unit': log_entry.get('_SYSTEMD_UNIT', 'unknown'),
                                'priority': log_entry.get('PRIORITY', '')
                            }
                            if error_info['message']:
                                errors.append(error_info)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            pass
            
        return errors

    def check_critical_conditions(self, temperatures: List[TempReading], gpu_info: Dict, metrics: Dict) -> List[str]:
        """Enhanced critical condition checking for Legion hardware"""
        warnings = []
        
        # Temperature warnings with component-specific thresholds
        for temp in temperatures:
            if 'CPU' in temp.name and temp.temp > self.thresholds['cpu_temp']:
                warnings.append(f"⚠️ Высокая температура CPU: {temp.temp:.1f}°C")
            elif 'GPU' in temp.name and temp.temp > self.thresholds['gpu_temp']:
                warnings.append(f"🔥 Высокая температура GPU: {temp.temp:.1f}°C")
            elif 'NVMe' in temp.name and temp.temp > self.thresholds['nvme_temp']:
                warnings.append(f"💾 Высокая температура SSD: {temp.temp:.1f}°C")
        
        # GPU warnings
        if gpu_info['available']:
            if gpu_info['power'] > self.thresholds['gpu_power']:
                warnings.append(f"⚡ Высокое потребление GPU: {gpu_info['power']:.1f}W")
            if gpu_info['throttle_reasons']:
                warnings.append("🚨 GPU THROTTLING активен!")
        
        # System warnings
        if metrics['cpu_usage'] > self.thresholds['cpu_usage']:
            warnings.append(f"💻 Высокая загрузка CPU: {metrics['cpu_usage']:.1f}%")
        if metrics['memory']['percent'] > self.thresholds['memory_usage']:
            warnings.append(f"🧠 Высокое использование RAM: {metrics['memory']['percent']:.1f}%")
        
        # Disk warnings
        for disk in metrics['disk_usage']:
            if disk['percent'] > self.thresholds['disk_usage']:
                warnings.append(f"💿 Диск {disk['device']}: {disk['percent']:.1f}%")
        
        return warnings

    def create_alert(self, level: str, component: str, message: str, value: float, threshold: float):
        """Create system alert with automatic cleanup"""
        alert = SystemAlert(
            timestamp=datetime.datetime.now().isoformat(),
            level=level,
            component=component,
            message=message,
            value=value,
            threshold=threshold
        )
        self.alerts.append(alert)
        
        # Limit alerts to prevent memory issues
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-50:]

    def get_color_for_temp(self, temp: float, critical: float) -> str:
        """Temperature-based color coding"""
        if temp >= critical:
            return Fore.RED + Style.BRIGHT
        elif temp >= critical * 0.85:
            return Fore.YELLOW + Style.BRIGHT
        elif temp >= critical * 0.7:
            return Fore.YELLOW
        else:
            return Fore.GREEN

    def get_color_for_usage(self, usage: float, critical: float = 90) -> str:
        """Usage-based color coding"""
        if usage >= critical:
            return Fore.RED + Style.BRIGHT
        elif usage >= critical * 0.8:
            return Fore.YELLOW
        else:
            return Fore.GREEN

    def analyze_system_state(self) -> Dict:
        """Complete system state analysis"""
        temperatures = self.get_all_temperatures()
        gpu_info = self.get_gpu_comprehensive_info()
        metrics = self.get_system_metrics()
        battery_info = self.get_battery_info()
        errors = self.get_system_errors_detailed()
        warnings = self.check_critical_conditions(temperatures, gpu_info, metrics)
        
        # Create alerts for critical conditions
        for temp in temperatures:
            if 'CPU' in temp.name and temp.temp > self.thresholds['cpu_temp']:
                self.create_alert('CRITICAL', 'cpu', f'High CPU Temperature: {temp.temp:.1f}°C',
                                temp.temp, self.thresholds['cpu_temp'])
            elif 'GPU' in temp.name and temp.temp > self.thresholds['gpu_temp']:
                self.create_alert('CRITICAL', 'gpu', f'High GPU Temperature: {temp.temp:.1f}°C',
                                temp.temp, self.thresholds['gpu_temp'])
        
        if gpu_info['throttle_reasons']:
            self.create_alert('CRITICAL', 'gpu', 'GPU Throttling Detected', 1, 0)
        
        # Build state dictionary
        state = {
            'timestamp': datetime.datetime.now().isoformat(),
            'temperatures': [{'name': t.name, 'temp': t.temp, 'source': t.source, 'critical': t.critical} for t in temperatures],
            'gpu': gpu_info,
            'system': metrics,
            'battery': battery_info,
            'errors': errors,
            'warnings': warnings,
            'alerts_today': len([a for a in self.alerts if a.timestamp.startswith(datetime.datetime.now().strftime('%Y-%m-%d'))])
        }
        
        return state

    def display_status(self):
        """Enhanced Legion-branded status display"""
        state = self.analyze_system_state()
        
        os.system('clear')
        
        # Legion 5 Pro branded header
        print(f"{Fore.CYAN + Style.BRIGHT}╔{'═' * 88}╗")
        print(f"║{' ' * 20}ENHANCED LEGION 5 PRO MONITOR v3.0{' ' * 20}║")
        print(f"║{' ' * 15}Advanced Thermal & Performance Monitoring{' ' * 16}║")
        print(f"╚{'═' * 88}╝{Style.RESET_ALL}")
        print()
        
        # Temperature monitoring section
        print(f"{Fore.WHITE + Style.BRIGHT}┌─ ТЕМПЕРАТУРЫ ───────────────────────────────────────────────────────┐{Style.RESET_ALL}")
        for temp_info in state['temperatures']:
            if 'CPU' in temp_info['name']:
                color = self.get_color_for_temp(temp_info['temp'], self.thresholds['cpu_temp'])
                icon = "🔥"
            elif 'GPU' in temp_info['name']:
                color = self.get_color_for_temp(temp_info['temp'], self.thresholds['gpu_temp'])
                icon = "🎮"
            elif 'NVMe' in temp_info['name']:
                color = self.get_color_for_temp(temp_info['temp'], self.thresholds['nvme_temp'])
                icon = "💾"
            else:
                color = self.get_color_for_temp(temp_info['temp'], 80)
                icon = "🌡️"
            
            critical_text = f"/{temp_info['critical']:.0f}°C" if temp_info['critical'] else ""
            print(f"│ {icon} {temp_info['name']:<20}: {color}{temp_info['temp']:5.1f}°C{critical_text}{Style.RESET_ALL} " +
                  f"({temp_info['source']}) │")
        print(f"{Fore.WHITE + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        
        # GPU section with enhanced status reporting
        if state['gpu']['available']:
            print(f"\n{Fore.WHITE + Style.BRIGHT}┌─ ВИДЕОКАРТА (RTX 3070 Mobile) ──────────────────────────────────────┐{Style.RESET_ALL}")
            
            if state['gpu']['status'] != 'nvidia-smi working':
                # GPU found but nvidia-smi issues
                status_color = Fore.YELLOW
                print(f"│ Статус: {status_color}{state['gpu']['status']:<50}{Style.RESET_ALL} │")
                print(f"│ Драйвер: {Fore.CYAN}{state['gpu']['driver_version']:<45}{Style.RESET_ALL} │")
                print(f"│ {Fore.YELLOW}💡 Решение: sudo reboot или переустановка драйверов{Style.RESET_ALL}           │")
            else:
                # GPU working normally
                gpu_temp_color = self.get_color_for_temp(state['gpu']['temp'], self.thresholds['gpu_temp'])
                power_color = self.get_color_for_usage(state['gpu']['power'], self.thresholds['gpu_power'])
                util_color = self.get_color_for_usage(state['gpu']['utilization'])
                
                print(f"│ Температура: {gpu_temp_color}{state['gpu']['temp']:5.1f}°C{Style.RESET_ALL}  │  " +
                      f"Мощность: {power_color}{state['gpu']['power']:5.1f}W{Style.RESET_ALL}  │  " +
                      f"Загрузка: {util_color}{state['gpu']['utilization']:4.1f}%{Style.RESET_ALL}  │")
                
                print(f"│ VRAM: {state['gpu']['memory_used']/1024:4.1f}GB/{state['gpu']['memory_total']/1024:4.1f}GB " +
                      f"({state['gpu']['memory_percent']:4.1f}%)  │  Частота: {Fore.GREEN}{state['gpu']['clock_core']:4.0f}MHz{Style.RESET_ALL}      │")
                
                if state['gpu']['throttle_reasons']:
                    print(f"│ {Fore.RED + Style.BRIGHT}🚨 THROTTLING АКТИВЕН!{Style.RESET_ALL}                                          │")
            
            print(f"{Fore.WHITE + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.WHITE + Style.BRIGHT}┌─ ВИДЕОКАРТА ────────────────────────────────────────────────────────┐{Style.RESET_ALL}")
            print(f"│ {Fore.RED}❌ GPU не обнаружена или драйверы не установлены{Style.RESET_ALL}                │")
            print(f"{Fore.WHITE + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        
        # System metrics section
        print(f"\n{Fore.WHITE + Style.BRIGHT}┌─ СИСТЕМА ───────────────────────────────────────────────────────────┐{Style.RESET_ALL}")
        cpu_color = self.get_color_for_usage(state['system']['cpu_usage'])
        mem_color = self.get_color_for_usage(state['system']['memory']['percent'])
        
        print(f"│ CPU: {cpu_color}{state['system']['cpu_usage']:5.1f}%{Style.RESET_ALL}  │  " +
              f"Частота: {Fore.CYAN}{state['system']['cpu_freq']:4.0f}MHz{Style.RESET_ALL}  │  " +
              f"RAM: {mem_color}{state['system']['memory']['percent']:4.1f}%{Style.RESET_ALL}        │")
        
        print(f"│ Память: {state['system']['memory']['used_gb']:4.1f}GB/{state['system']['memory']['total_gb']:4.1f}GB  │  " +
              f"Load: {Fore.YELLOW}{state['system']['load_average']['1m']:4.2f}{Style.RESET_ALL}  │  " +
              f"Время: {Fore.GREEN}{state['system']['uptime_hours']:4.1f}h{Style.RESET_ALL}    │")
        
        # Battery information
        if state['battery']['present']:
            battery_color = Fore.GREEN if state['battery']['charging'] else Fore.YELLOW
            print(f"│ Питание: {battery_color}{state['battery']['power_source']}{Style.RESET_ALL}  │  " +
                  f"Батарея: {battery_color}{state['battery']['percent']:3.0f}%{Style.RESET_ALL}  │  " +
                  f"Напряжение: {Fore.CYAN}{state['battery']['voltage']:.2f}V{Style.RESET_ALL}    │")
        
        print(f"{Fore.WHITE + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        
        # Disk usage (filtered)
        if state['system']['disk_usage']:
            print(f"\n{Fore.WHITE + Style.BRIGHT}┌─ ДИСКИ ─────────────────────────────────────────────────────────────┐{Style.RESET_ALL}")
            for disk in state['system']['disk_usage'][:3]:  # Show first 3 disks
                disk_color = self.get_color_for_usage(disk['percent'], self.thresholds['disk_usage'])
                print(f"│ {disk['device']:<15}: {disk_color}{disk['percent']:5.1f}%{Style.RESET_ALL} " +
                      f"({disk['used_gb']:4.1f}GB/{disk['total_gb']:4.1f}GB) {disk['mountpoint']:<10} │")
            print(f"{Fore.WHITE + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        
        # Warnings section
        if state['warnings']:
            print(f"\n{Fore.RED + Style.BRIGHT}┌─ ПРЕДУПРЕЖДЕНИЯ ────────────────────────────────────────────────────┐{Style.RESET_ALL}")
            for warning in state['warnings'][:5]:  # Show max 5 warnings
                print(f"│ {Fore.RED}{warning:<70}{Style.RESET_ALL} │")
            print(f"{Fore.RED + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        
        # Recent system errors
        if state['errors']:
            print(f"\n{Fore.YELLOW + Style.BRIGHT}┌─ СИСТЕМНЫЕ ОШИБКИ ──────────────────────────────────────────────────┐{Style.RESET_ALL}")
            for error in state['errors'][:3]:  # Show max 3 recent errors
                error_msg = error['message'][:60] + "..." if len(error['message']) > 60 else error['message']
                print(f"│ {Fore.YELLOW}{error_msg:<70}{Style.RESET_ALL} │")
            print(f"{Fore.YELLOW + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        
        # Control panel
        print(f"\n{Fore.WHITE + Style.BRIGHT}┌─ УПРАВЛЕНИЕ ────────────────────────────────────────────────────────┐{Style.RESET_ALL}")
        print(f"│ {Fore.GREEN}q{Style.RESET_ALL} - Выход  │  {Fore.GREEN}s{Style.RESET_ALL} - Сохранить  │  " +
              f"{Fore.GREEN}r{Style.RESET_ALL} - Сброс  │  Alerts: {Fore.YELLOW}{state['alerts_today']}{Style.RESET_ALL}        │")
        print(f"│ Лог: {Fore.CYAN}{self.log_file:<60}{Style.RESET_ALL} │")
        print(f"{Fore.WHITE + Style.BRIGHT}└──────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")
        
        return state

    def export_data(self, data: Dict):
        """Export system data in specified format"""
        try:
            if self.export_format == 'json':
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.write('\n')
            elif self.export_format == 'csv':
                # CSV export with key metrics
                csv_line = f"{data['timestamp']},{data['system']['cpu_usage']:.1f},{data['system']['memory']['percent']:.1f}"
                if data['gpu']['available']:
                    csv_line += f",{data['gpu']['temp']:.1f},{data['gpu']['power']:.1f}"
                else:
                    csv_line += ",0,0"
                
                # Add temperature data
                for temp in data['temperatures']:
                    csv_line += f",{temp['temp']:.1f}"
                
                csv_line += f",{len(data['warnings'])}\n"
                
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(csv_line)
            else:  # txt format
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{data['timestamp']}] ")
                    
                    # Temperature summary
                    for temp in data['temperatures']:
                        f.write(f"{temp['name']}: {temp['temp']:.1f}°C | ")
                    
                    # GPU and system summary
                    if data['gpu']['available']:
                        f.write(f"GPU: {data['gpu']['temp']:.1f}°C/{data['gpu']['power']:.1f}W | ")
                    f.write(f"CPU: {data['system']['cpu_usage']:.1f}% | ")
                    f.write(f"RAM: {data['system']['memory']['percent']:.1f}%\n")
                    
                    # Warnings
                    for warning in data['warnings']:
                        f.write(f"  WARNING: {warning}\n")
                    f.write("\n")
                    
        except Exception as e:
            print(f"Export error: {e}")

    def input_handler(self):
        """Handle user input for interactive controls"""
        while self.running:
            try:
                key = input().strip().lower()
                if key == 'q':
                    self.running = False
                    break
                elif key == 's':
                    print(f"\n{Fore.GREEN}✓ Data saved to {self.log_file}{Style.RESET_ALL}")
                    time.sleep(1)
                elif key == 'r':
                    self.alerts = []
                    print(f"\n{Fore.GREEN}✓ Alerts reset{Style.RESET_ALL}")
                    time.sleep(1)
            except (EOFError, KeyboardInterrupt):
                self.running = False
                break

    def run(self, interval: int = 2):
        """Main monitoring loop with enhanced Legion-specific features"""
        print(f"{Fore.GREEN}🚀 Starting Enhanced Legion 5 Pro Monitor...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Temperature sensors: {len(self.temp_sensors)} discovered{Style.RESET_ALL}")
        print(f"{Fore.CYAN}GPU: {'Available' if self.gpu_available else 'Not available'}{Style.RESET_ALL}")
        time.sleep(3)
        
        # Start input handler thread
        input_thread = threading.Thread(target=self.input_handler, daemon=True)
        input_thread.start()
        
        try:
            while self.running:
                state = self.display_status()
                self.export_data(state)
                self.data_history.append(state)
                
                # Limit history to prevent memory issues
                if len(self.data_history) > 300:
                    self.data_history = self.data_history[-200:]
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            pass
        finally:
            print(f"\n\n{Fore.GREEN}✅ Enhanced Legion Monitor stopped. Data saved to {self.log_file}{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description='Enhanced Legion 5 Pro System Monitor v3.0')
    parser.add_argument('--export', choices=['json', 'txt', 'csv'], default='txt',
                        help='Export format for data logging')
    parser.add_argument('--interval', type=int, default=2,
                        help='Update interval in seconds')
    parser.add_argument('--test', action='store_true',
                        help='Test run - show sensor discovery and exit')
    
    args = parser.parse_args()
    
    monitor = EnhancedLegionMonitor(export_format=args.export)
    
    if args.test:
        print(f"{Fore.CYAN}🔍 Enhanced Legion Monitor Sensor Test:{Style.RESET_ALL}")
        temperatures = monitor.get_all_temperatures()
        gpu_info = monitor.get_gpu_comprehensive_info()
        
        print(f"\n{Fore.GREEN}Temperature Sensors:{Style.RESET_ALL}")
        for temp in temperatures:
            color = monitor.get_color_for_temp(temp.temp, temp.critical or 80)
            print(f"  {color}{temp.name}: {temp.temp:.1f}°C ({temp.source}){Style.RESET_ALL}")
        
        print(f"\n{Fore.GREEN}GPU Status:{Style.RESET_ALL}")
        if gpu_info['available']:
            if gpu_info['status'] == 'nvidia-smi working':
                print(f"  🎮 RTX 3070: {gpu_info['temp']:.1f}°C, {gpu_info['power']:.1f}W")
            else:
                print(f"  🎮 RTX 3070: {Fore.YELLOW}{gpu_info['status']}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.RED}❌ GPU not available{Style.RESET_ALL}")
        
        return
    
    monitor.run(interval=args.interval)

def signal_handler(signum, frame):
    print(f"\n{Fore.YELLOW}Shutting down Enhanced Legion Monitor...{Style.RESET_ALL}")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main() 