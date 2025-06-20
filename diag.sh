#!/bin/bash
echo "🔍 ПОЛНАЯ ДИАГНОСТИКА DRM КОНФЛИКТОВ"
echo "===================================="

echo "📊 1. GPU устройства:"
lspci | grep -E "(VGA|3D|Display)"

echo ""
echo "📊 2. DRM устройства:"
ls -la /dev/dri/

echo ""
echo "📊 3. Кто использует DRM:"
sudo lsof /dev/dri/card* 2>/dev/null || echo "Никто не использует DRM активно"

echo ""
echo "📊 4. Загруженные графические драйверы:"
lsmod | grep -E "(nvidia|amdgpu|radeon|nouveau|i915)"

echo ""
echo "📊 5. X11 провайдеры:"
xrandr --listproviders 2>/dev/null || echo "Ошибка получения провайдеров"

echo ""
echo "📊 6. Активные дисплеи:"
xrandr | grep " connected"

echo ""
echo "📊 7. NVIDIA информация:"
nvidia-smi --query-gpu=name,driver_version,pci.bus_id --format=csv,noheader

echo ""
echo "📊 8. Последние DRM ошибки:"
journalctl --since "1 hour ago" | grep -E "Failed to grab modeset|nvidia-drm" | tail -5

echo ""
echo "📊 9. GDM статус:"
systemctl status gdm --no-pager -l | head -10

echo ""
echo "📊 10. Текущая сессия:"
echo "Тип: $XDG_SESSION_TYPE"
echo "Рабочий стол: $XDG_CURRENT_DESKTOP"


# Быстрая проверка успешности исправления simple-framebuffer

echo "🔍 ПРОВЕРКА ИСПРАВЛЕНИЯ SIMPLE-FRAMEBUFFER"
echo "========================================"

# 1. Проверка исчезновения simple-framebuffer
echo "📊 1. Проверка simple-framebuffer:"
SIMPLE_FB=$(ls -la /sys/class/drm/ | grep -c simple)
if [ "$SIMPLE_FB" -eq 0 ]; then
    echo "✅ SUCCESS: simple-framebuffer ИСЧЕЗ!"
    SUCCESS_COUNT=1
else
    echo "❌ FAIL: simple-framebuffer все еще присутствует"
    ls -la /sys/class/drm/ | grep simple
    SUCCESS_COUNT=0
fi

echo ""

# 2. Проверка DRM устройств  
echo "📊 2. Текущие DRM устройства:"
for card in /sys/class/drm/card*; do
    if [ -d "$card" ]; then
        cardname=$(basename "$card")
        driver=$(cat "$card/device/uevent" 2>/dev/null | grep DRIVER | cut -d= -f2)
        echo "   $cardname: $driver"
    fi
done

echo ""

# 3. Проверка modeset ошибок с загрузки
echo "📊 3. Modeset ошибки с загрузки:"
MODESET_ERRORS=$(journalctl -b | grep -c "Failed to grab modeset")
if [ "$MODESET_ERRORS" -eq 0 ]; then
    echo "✅ SUCCESS: Нет modeset ошибок с загрузки!"
    ((SUCCESS_COUNT++))
else
    echo "❌ FAIL: Найдено $MODESET_ERRORS modeset ошибок"
    journalctl -b | grep "Failed to grab modeset" | tail -3
fi

echo ""

# 4. Проверка недавних ошибок
echo "📊 4. Modeset ошибки за последние 5 минут:"
RECENT_ERRORS=$(journalctl --since "5 minutes ago" | grep -c "Failed to grab modeset")
if [ "$RECENT_ERRORS" -eq 0 ]; then
    echo "✅ SUCCESS: Нет недавних modeset ошибок!"
    ((SUCCESS_COUNT++))
else
    echo "❌ FAIL: Найдено $RECENT_ERRORS недавних ошибок"
fi

echo ""

# 5. Проверка GRUB параметров
echo "📊 5. GRUB параметры:"
if grep -q "video=simplefb:off" /etc/default/grub; then
    echo "✅ SUCCESS: simplefb:off присутствует в GRUB"
    ((SUCCESS_COUNT++))
else
    echo "❌ FAIL: simplefb:off НЕ найден в GRUB"
fi

echo ""

# 6. Итоговая оценка
echo "📊 ИТОГОВАЯ ОЦЕНКА:"
echo "=================="
if [ "$SUCCESS_COUNT" -ge 3 ]; then
    echo "🎉 ОТЛИЧНО! Исправление СРАБОТАЛО!"
    echo "   ✅ $SUCCESS_COUNT/4 проверок пройдено"
    echo ""
    echo "💡 Рекомендации:"
    echo "   - Протестируйте стабильность в течение дня"
    echo "   - Больше никаких изменений не требуется"
elif [ "$SUCCESS_COUNT" -ge 2 ]; then
    echo "⚠️  ЧАСТИЧНО РАБОТАЕТ"
    echo "   ⚠️  $SUCCESS_COUNT/4 проверок пройдено"
    echo ""
    echo "💡 Рекомендации:"
    echo "   - Добавьте ШАГ 2 (blacklist framebuffer модулей)"
    echo "   - Перезагрузитесь и проверьте снова"
else
    echo "❌ НЕУДАЧА - исправление НЕ сработало"
    echo "   ❌ Только $SUCCESS_COUNT/4 проверок пройдено"
    echo ""
    echo "💡 Рекомендации:"
    echo "   - Проверьте правильность GRUB параметров"
    echo "   - Добавьте ШАГ 2 и ШАГ 4"
    echo "   - Выполните команду: sudo update-grub && sudo reboot"
fi

echo ""
echo "🔄 Мониторинг в реальном времени (Ctrl+C для выхода):"
echo "======================================================"
echo "Следите за новыми ошибками..."
journalctl -f | grep --line-buffered -E "Failed to grab|nvidia-drm|simple" &
MONITOR_PID=$!

# Автоматическая остановка через 30 секунд
sleep 30
kill $MONITOR_PID 2>/dev/null
echo ""
echo "✅ Проверка завершена. Если нет новых ошибок - все работает!"