import logging
import os
import torch
import cv2
import numpy as np
from PIL import Image
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ========== ТВОЙ ТОКЕН ==========
TELEGRAM_TOKEN = '8747690008:AAGQVfpp9xUbfyuPObOyt3kJVOUZ1rjnQck'
# ================================

# Загружаем модель при старте бота
print("🔄 Загрузка модели нейросети...")
from model import BiSeNet

n_classes = 19
net = BiSeNet(n_classes=n_classes)
net.load_state_dict(torch.load('model.pth', map_location='cpu'))
net.eval()
print("✅ Модель загружена!")

# Цвета для волос (BGR формат для OpenCV)
COLORS = {
    '🖤 Черный': (0, 0, 0),
    '💛 Золотой (блонд)': (0, 215, 255),
    '❤️ Красный': (0, 0, 255),
    '🤎 Коричневый': (19, 69, 139),
    '💙 Синий': (255, 0, 0),
    '💚 Зеленый': (0, 255, 0),
    '💜 Фиолетовый': (128, 0, 128),
    '🧡 Рыжий': (0, 165, 255),
}

def change_hair_color(image_path, output_path, color_bgr):
    """Меняет цвет волос используя нейросеть"""
    
    # Загружаем и подготавливаем изображение
    img = Image.open(image_path).convert('RGB')
    original_size = img.size
    
    # Ресайзим для нейросети
    img_resized = img.resize((512, 512))
    img_tensor = torch.tensor(np.array(img_resized)).permute(2,0,1).unsqueeze(0).float()
    img_tensor = img_tensor / 255.0  # нормализация
    
    # Получаем маску волос через нейросеть
    with torch.no_grad():
        out = net(img_tensor)[0]
        parsing = out.squeeze(0).argmax(0).numpy()
    
    # Класс 17 - это волосы в данной модели
    hair_mask = (parsing == 17).astype(np.uint8) * 255
    
    # Улучшаем маску
    kernel = np.ones((5,5), np.uint8)
    hair_mask = cv2.morphologyEx(hair_mask, cv2.MORPH_CLOSE, kernel)
    
    # Ресайзим маску обратно до оригинального размера
    hair_mask = cv2.resize(hair_mask, original_size, interpolation=cv2.INTER_LINEAR)
    
    # Загружаем оригинальное изображение для обработки
    img_original = cv2.imread(image_path)
    
    # Создаем копию и меняем цвет волос
    result = img_original.copy()
    
    # Накладываем новый цвет только на область волос
    for c in range(3):
        result[:,:,c] = np.where(
            hair_mask > 0,
            color_bgr[c],
            img_original[:,:,c]
        )
    
    # Сохраняем результат
    cv2.imwrite(output_path, result)
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '👋 Привет! Я бот для смены цвета волос с помощью нейросети.\n\n'
        '📸 Отправь фото, выбери цвет, и я изменю ТОЛЬКО волосы!'
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive('input.jpg')
        
        context.user_data['awaiting_color'] = True
        
        # Создаем клавиатуру с цветами
        color_list = list(COLORS.keys())
        keyboard = []
        for i in range(0, len(color_list), 2):
            if i+1 < len(color_list):
                keyboard.append([color_list[i], color_list[i+1]])
            else:
                keyboard.append([color_list[i]])
        keyboard.append(['❌ Отмена'])
        
        await update.message.reply_text(
            '✅ Фото получил! Теперь выбери цвет волос:',
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Ошибка: {e}')

async def handle_color_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_color'):
        return
    
    color_name = update.message.text
    
    if color_name == '❌ Отмена':
        context.user_data['awaiting_color'] = False
        await update.message.reply_text('❌ Отменено', reply_markup=ReplyKeyboardRemove())
        return
    
    if color_name not in COLORS:
        await update.message.reply_text('❌ Выбери цвет из кнопок!')
        return
    
    try:
        await update.message.reply_text(
            f'🎨 Обрабатываю... (цвет: {color_name})',
            reply_markup=ReplyKeyboardRemove()
        )
        
        color_bgr = COLORS[color_name]
        
        success = change_hair_color('input.jpg', 'output.jpg', color_bgr)
        
        if success and os.path.exists('output.jpg'):
            with open('output.jpg', 'rb') as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f'✅ Готово! Цвет: {color_name}'
                )
        else:
            await update.message.reply_text('❌ Не удалось обработать. Попробуй другое фото.')
        
        # Чистим файлы
        try:
            os.remove('input.jpg')
            os.remove('output.jpg')
        except:
            pass
        
        context.user_data['awaiting_color'] = False
        
    except Exception as e:
        await update.message.reply_text(f'❌ Ошибка: {e}')
        context.user_data['awaiting_color'] = False

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_color_choice))
    
    print('🚀 Бот с локальной нейросетью запущен!')
    app.run_polling()

if __name__ == '__main__':
    main()