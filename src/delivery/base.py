from abc import ABC, abstractmethod

class BaseDeliveryProvider(ABC):
    @abstractmethod
    def send(self, file_path: str, provider_config: dict, global_config: dict) -> bool:
        """
        Метод отправки файла.
        :param file_path: Путь к сгенерированному Excel-файлу
        :param provider_config: Настройки этого провайдера из конфига отчета (jobs/config.yaml)
        :param global_config: Глобальные доступы из config/main.toml
        :return: True если отправка успешна, иначе False
        """
        pass