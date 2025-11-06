#!/usr/bin/env python3
"""
Sistema de Notificações
=======================
Sistema para enviar notificações sobre o status das execuções.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class NotificationType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Notification:
    type: NotificationType
    title: str
    message: str
    timestamp: datetime
    details: Optional[Dict] = None


class NotificationManager:
    """Gerencia notificações do sistema"""
    
    def __init__(self):
        self.notifications: List[Notification] = []
        self.logger = logging.getLogger(__name__)
        
    def add_notification(self, notification_type: NotificationType, title: str, 
                        message: str, details: Optional[Dict] = None):
        """Adiciona uma nova notificação"""
        notification = Notification(
            type=notification_type,
            title=title,
            message=message,
            timestamp=datetime.now(),
            details=details
        )
        self.notifications.append(notification)
        
        # Log da notificação
        log_message = f"[{notification_type.value.upper()}] {title}: {message}"
        if notification_type == NotificationType.ERROR:
            self.logger.error(log_message)
        elif notification_type == NotificationType.WARNING:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
            
    def success(self, title: str, message: str, details: Optional[Dict] = None):
        """Adiciona notificação de sucesso"""
        self.add_notification(NotificationType.SUCCESS, title, message, details)
        
    def error(self, title: str, message: str, details: Optional[Dict] = None):
        """Adiciona notificação de erro"""
        self.add_notification(NotificationType.ERROR, title, message, details)
        
    def warning(self, title: str, message: str, details: Optional[Dict] = None):
        """Adiciona notificação de aviso"""
        self.add_notification(NotificationType.WARNING, title, message, details)
        
    def info(self, title: str, message: str, details: Optional[Dict] = None):
        """Adiciona notificação informativa"""
        self.add_notification(NotificationType.INFO, title, message, details)
        
    def get_recent_notifications(self, limit: int = 10) -> List[Notification]:
        """Retorna as notificações mais recentes"""
        return sorted(self.notifications, key=lambda x: x.timestamp, reverse=True)[:limit]
        
    def get_notifications_by_type(self, notification_type: NotificationType) -> List[Notification]:
        """Retorna notificações por tipo"""
        return [n for n in self.notifications if n.type == notification_type]
        
    def clear_notifications(self):
        """Limpa todas as notificações"""
        self.notifications.clear()
        
    def generate_summary(self) -> Dict:
        """Gera um resumo das notificações"""
        total = len(self.notifications)
        by_type = {}
        
        for notification_type in NotificationType:
            by_type[notification_type.value] = len(
                self.get_notifications_by_type(notification_type)
            )
            
        return {
            "total": total,
            "by_type": by_type,
            "recent": [n.title for n in self.get_recent_notifications(5)]
        }


# Instância global do gerenciador de notificações
notification_manager = NotificationManager()


def notify_extraction_start(script_name: str):
    """Notifica início de extração"""
    notification_manager.info(
        "Extração Iniciada",
        f"Iniciando extração: {script_name}",
        {"script": script_name, "timestamp": datetime.now().isoformat()}
    )


def notify_extraction_success(script_name: str, records_count: int):
    """Notifica sucesso na extração"""
    notification_manager.success(
        "Extração Concluída",
        f"Extração {script_name} concluída com {records_count} registros",
        {"script": script_name, "records": records_count}
    )


def notify_extraction_error(script_name: str, error: str):
    """Notifica erro na extração"""
    notification_manager.error(
        "Erro na Extração",
        f"Falha na extração {script_name}: {error}",
        {"script": script_name, "error": error}
    )


def notify_whatsapp_send_success(groups_count: int):
    """Notifica sucesso no envio do WhatsApp"""
    notification_manager.success(
        "WhatsApp Enviado",
        f"Mensagens enviadas para {groups_count} grupos",
        {"groups": groups_count}
    )


def notify_whatsapp_send_error(error: str):
    """Notifica erro no envio do WhatsApp"""
    notification_manager.error(
        "Erro no WhatsApp",
        f"Falha no envio: {error}",
        {"error": error}
    )


def notify_meta_capture_success(metas: Dict[str, float]):
    """Notifica sucesso na captura de metas"""
    notification_manager.success(
        "Metas Capturadas",
        f"Metas capturadas: {', '.join([f'{k}: R${v:,.2f}' for k, v in metas.items()])}",
        {"metas": metas}
    )
