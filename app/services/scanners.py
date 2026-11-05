# app/services/scanners.py
from werkzeug.security import generate_password_hash
from ..extensions import db
from ..models.usuario import Usuario

class ScannerService:
    @staticmethod
    def listar(padre_id):
        return Usuario.query.filter_by(usuario_padre_id=padre_id, es_scanner=True).all()

    @staticmethod
    def crear(padre_id, nombre, email, password):
        if Usuario.query.filter_by(email=email).first():
            return None, 'El email ya esta registrado'
            
        scanner = Usuario(
            nombre=nombre,
            email=email,
            es_scanner=True,
            usuario_padre_id=padre_id,
            activo=True
        )
        scanner.set_password(password)
        
        try:
            db.session.add(scanner)
            db.session.commit()
            return scanner, None
        except Exception as e:
            db.session.rollback()
            return None, str(e)

    @staticmethod
    def eliminar(scanner_id, padre_id):
        scanner = Usuario.query.filter_by(id=scanner_id, usuario_padre_id=padre_id, es_scanner=True).first()
        if not scanner:
            return False, 'Scanner no encontrado'
        try:
            db.session.delete(scanner)
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)
