from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from ..database import crud

class DbUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            
        if user:
            # Обновляем или создаем пользователя при каждом запросе
            await crud.register_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            # Проверяем обязательную подписку и правила
            if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                pass # Разрешаем /start
            elif isinstance(event, CallbackQuery) and event.data in ["check_mandatory_sub", "show_tos", "back_to_mandatory"]:
                pass # Разрешаем кнопки подписки
            else:
                from ..config import db_settings
                main_channel_id = db_settings.get("main_channel_id")
                if main_channel_id:
                    db_user = await crud.get_user(user.id)
                    if not db_user or not db_user.tos_accepted:
                        if isinstance(event, CallbackQuery):
                            await event.answer("⚠️ Пожалуйста, примите правила и подпишитесь на канал через /start", show_alert=True)
                        elif isinstance(event, Message):
                            await event.answer("⚠️ <b>Обязательное действие</b>\nПожалуйста, введите /start чтобы подписаться на канал и принять правила.")
                        return # Блокируем дальнейшее выполнение
            
        return await handler(event, data)
