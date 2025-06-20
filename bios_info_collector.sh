#!/bin/bash

echo "🔍 ПОЛНАЯ ИНФОРМАЦИЯ О BIOS/UEFI"
echo "====================================="
echo ""

echo "📊 1. БАЗОВАЯ ИНФОРМАЦИЯ BIOS:"
echo "------------------------------"
sudo dmidecode -t bios
echo ""

echo "📊 2. СИСТЕМНАЯ ИНФОРМАЦИЯ:"
echo "-------------------------"
sudo dmidecode -t system
echo ""

echo "📊 3. ИНФОРМАЦИЯ О МАТЕРИНСКОЙ ПЛАТЕ:"
echo "-----------------------------------"
sudo dmidecode -t baseboard
echo ""

echo "📊 4. UEFI BOOT НАСТРОЙКИ:"
echo "------------------------"
sudo efibootmgr -v 2>/dev/null || echo "UEFI boot manager недоступен"
echo ""

echo "📊 5. UEFI ПЕРЕМЕННЫЕ (ВАЖНЫЕ):"
echo "-----------------------------"
echo "SecureBoot:"
cat /sys/firmware/efi/efivars/SecureBoot* 2>/dev/null | hexdump -C | head -3 || echo "SecureBoot переменная недоступна"
echo ""
echo "BootCurrent:"
cat /sys/firmware/efi/efivars/BootCurrent* 2>/dev/null | hexdump -C | head -3 || echo "BootCurrent недоступен"
echo ""

echo "📊 6. ЗАГРУЗОЧНЫЕ СООБЩЕНИЯ BIOS:"
echo "-------------------------------"
sudo dmesg | grep -i -E "(bios|uefi|efi|firmware|acpi|secure.*boot|csm|legacy)" | head -20
echo ""

echo "📊 7. ПРОЦЕССОР И ФУНКЦИИ:"
echo "------------------------"
lscpu | grep -E "(Model name|Flags|Virtualization|Hypervisor)"
echo ""

echo "📊 8. PCI ИНФОРМАЦИЯ (GPU и контроллеры):"
echo "---------------------------------------"
lspci | grep -E "(VGA|Display|3D|Host bridge|PCI bridge)"
echo ""

echo "📊 9. ACPI ТАБЛИЦЫ:"
echo "-----------------"
sudo dmesg | grep -i "acpi.*table" | head -10
echo ""

echo "📊 10. ЗАГРУЗОЧНЫЕ ПАРАМЕТРЫ KERNEL:"
echo "---------------------------------"
cat /proc/cmdline
echo ""

echo "📊 11. ИНФОРМАЦИЯ О FIRMWARE:"
echo "---------------------------"
ls -la /sys/firmware/efi/efivars/ 2>/dev/null | wc -l && echo "UEFI переменных найдено" || echo "Система не UEFI"
echo ""

echo "📊 12. СПЕЦИФИЧНЫЕ НАСТРОЙКИ ДЛЯ LEGION:"
echo "-------------------------------------"
sudo dmidecode | grep -i -A5 -B5 "legion\|lenovo\|ideapad"
echo ""

echo "📊 13. ВИДЕОКАРТА И ДИСПЛЕЙ ДЕТАЛИ:"
echo "---------------------------------"
sudo lshw -c display -short 2>/dev/null || echo "lshw недоступен"
echo ""

echo "📊 14. IOMMU/VIRTUALIZATION:"
echo "---------------------------"
sudo dmesg | grep -i -E "(iommu|virtualization|vt-d|amd-vi)" | head -5
echo ""

echo "📊 15. CSM/LEGACY ИНДИКАТОРЫ:"
echo "---------------------------"
sudo dmesg | grep -i -E "(csm|legacy|bios.*mode|boot.*mode)" | head -5
echo ""

echo "✅ СБОР ИНФОРМАЦИИ ЗАВЕРШЕН"
echo "============================"