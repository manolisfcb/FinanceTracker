from abc import ABC, abstractmethod

class Mensaje(ABC):
    def __init__(self, lang):
        self.lang = lang
    
    @abstractmethod
    def create_message(self, key):
        pass

class WarningPt(Mensaje):
    LINKERROR = "Link inválido"
    LIMITEXCEEDED = "Limite de tentativas excedido"
    INVALIDPARAMETER = "Parâmetro inválido"

class WarningEs(Mensaje):
    LINKERROR = "Enlace inválido"
    LIMITEXCEEDED = "Límite de intentos excedido"
    INVALIDPARAMETER = "Parámetro inválido"

class WarningEn(Mensaje):
    LINKERROR = "Invalid link"
    LIMITEXCEEDED = "Limit exceeded"
    INVALIDPARAMETER = "Invalid parameter"

class warnings():
    def __init__(self, lang):
        self.lang = lang
        self.WARNINGS = self.get_warning(lang)
        
    def get_warning(self, key):
        return WARNING[self.lang]



class messenger():
    def __init__(self, lang):
        self.lang = lang
        self.WARNINGS = warnings(lang)
        # self.error = Errors(lang)
        # self.info = Info(lang)
        
mensaje = Mensaje("es")
print(mensaje.lang)
print(mensaje.WARNINGS.warnings)  # {"warning": "Aviso", "warnings":