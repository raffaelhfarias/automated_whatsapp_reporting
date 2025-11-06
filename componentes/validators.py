#!/usr/bin/env python3
"""
Sistema de Validação de Dados
=============================
Validação e limpeza de dados extraídos.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import logging


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    cleaned_data: Optional[Dict] = None
    is_today: bool = False


class DataValidator:
    """Validador de dados extraídos"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def validate_monetary_value(self, value: str) -> Tuple[bool, Optional[float], List[str]]:
        """Valida e converte valor monetário"""
        errors = []
        
        if not value:
            errors.append("Valor monetário está vazio")
            return False, None, errors
            
        # Remove R$, espaços e converte vírgula para ponto
        cleaned = value.replace('R$', '').replace(' ', '').strip()
        cleaned = cleaned.replace('.', '').replace(',', '.')
        
        try:
            float_value = float(cleaned)
            if float_value < 0:
                errors.append("Valor monetário não pode ser negativo")
                return False, None, errors
            return True, float_value, errors
        except ValueError:
            errors.append(f"Valor monetário inválido: '{value}'")
            return False, None, errors
            
    def validate_company_name(self, name: str) -> Tuple[bool, str, List[str]]:
        """Valida nome da empresa"""
        errors = []
        
        if not name:
            errors.append("Nome da empresa está vazio")
            return False, "", errors
            
        # Remove espaços extras
        cleaned = " ".join(name.split())
        
        # Verifica se tem pelo menos 3 caracteres
        if len(cleaned) < 3:
            errors.append("Nome da empresa muito curto")
            return False, cleaned, errors
            
        return True, cleaned, errors
        
    def validate_store_name(self, name: str) -> Tuple[bool, str, List[str]]:
        """Valida nome da loja"""
        errors = []
        
        if not name:
            errors.append("Nome da loja está vazio")
            return False, "", errors
            
        # Remove espaços extras
        cleaned = " ".join(name.split())
        
        # Verifica se tem pelo menos 2 caracteres
        if len(cleaned) < 2:
            errors.append("Nome da loja muito curto")
            return False, cleaned, errors
            
        return True, cleaned, errors
        
    def validate_csv_data(self, data: List[List], expected_columns: int) -> ValidationResult:
        """Valida dados de CSV"""
        errors = []
        warnings = []
        cleaned_data = []
        
        if not data:
            errors.append("Dados CSV estão vazios")
            return ValidationResult(False, errors, warnings)
            
        for i, row in enumerate(data, 1):
            if len(row) != expected_columns:
                errors.append(f"Linha {i}: número incorreto de colunas (esperado: {expected_columns}, encontrado: {len(row)})")
                continue
                
            # Valida cada linha
            row_errors = []
            row_warnings = []
            cleaned_row = []
            
            for j, cell in enumerate(row):
                if not cell or str(cell).strip() == "":
                    row_warnings.append(f"Linha {i}, coluna {j+1}: célula vazia")
                    cleaned_row.append("")
                else:
                    cleaned_row.append(str(cell).strip())
                    
            if row_errors:
                errors.extend(row_errors)
            if row_warnings:
                warnings.extend(row_warnings)
                
            cleaned_data.append(cleaned_row)
            
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, {"data": cleaned_data})
        
    def validate_meta_data(self, metas: Dict[str, float]) -> ValidationResult:
        """Valida dados de meta"""
        errors = []
        warnings = []
        
        expected_keys = ['PEF', 'EUDORA', 'LOJA']
        
        for key in expected_keys:
            if key not in metas:
                errors.append(f"Meta '{key}' não encontrada")
                continue
                
            value = metas[key]
            if not isinstance(value, (int, float)):
                errors.append(f"Meta '{key}' deve ser um número")
                continue
                
            if value < 0:
                errors.append(f"Meta '{key}' não pode ser negativa")
                continue
                
            if value == 0:
                warnings.append(f"Meta '{key}' é zero")
                
        # Verifica se há metas extras
        extra_keys = set(metas.keys()) - set(expected_keys)
        if extra_keys:
            warnings.append(f"Metas extras encontradas: {', '.join(extra_keys)}")
            
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, {"metas": metas})
        
    def validate_date_format(self, date_str: str) -> Tuple[bool, Optional[str], List[str]]:
        """Valida formato de data"""
        errors = []
        
        if not date_str:
            errors.append("Data está vazia")
            return False, None, errors
            
        # Padrão dd/mm/yyyy
        pattern = r'^\d{2}/\d{2}/\d{4}$'
        if not re.match(pattern, date_str):
            errors.append(f"Formato de data inválido: '{date_str}' (esperado: dd/mm/yyyy)")
            return False, None, errors
            
        try:
            # Tenta converter para datetime para validar
            datetime.strptime(date_str, '%d/%m/%Y')
            return True, date_str, errors
        except ValueError:
            errors.append(f"Data inválida: '{date_str}'")
            return False, None, errors
            
    def clean_and_validate_extraction_data(self, data: List[List], data_type: str) -> ValidationResult:
        """Limpa e valida dados de extração"""
        errors = []
        warnings = []
        cleaned_data = []
        
        if data_type == "loja":
            expected_columns = 2
            name_validator = self.validate_store_name
        elif data_type in ["vd", "pef"]:
            expected_columns = 2
            name_validator = self.validate_company_name
        else:
            errors.append(f"Tipo de dados desconhecido: {data_type}")
            return ValidationResult(False, errors, warnings)
            
        for i, row in enumerate(data, 1):
            if len(row) != expected_columns:
                errors.append(f"Linha {i}: número incorreto de colunas")
                continue
                
            # Valida nome
            name_valid, name_cleaned, name_errors = name_validator(row[0])
            if not name_valid:
                errors.extend([f"Linha {i}: {error}" for error in name_errors])
                continue
                
            # Valida valor monetário
            value_valid, value_cleaned, value_errors = self.validate_monetary_value(row[1])
            if not value_valid:
                errors.extend([f"Linha {i}: {error}" for error in value_errors])
                continue
                
            cleaned_data.append([name_cleaned, str(value_cleaned)])
            
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, {"data": cleaned_data})


# Instância global do validador
data_validator = DataValidator()


def validate_extraction_file(file_path: str, data_type: str) -> ValidationResult:
    """Valida arquivo de extração e marca se é do dia (pela data de modificação)."""
    import csv, os
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Pula cabeçalho
            data = list(reader)
        vr = data_validator.clean_and_validate_extraction_data(data, data_type)
        try:
            from datetime import datetime
            mtime = os.path.getmtime(file_path)
            dt = datetime.fromtimestamp(mtime)
            vr.is_today = dt.date() == datetime.today().date()
        except Exception:
            vr.is_today = False
        return vr
    except FileNotFoundError:
        return ValidationResult(False, [f"Arquivo não encontrado: {file_path}"], [], is_today=False)
    except Exception as e:
        return ValidationResult(False, [f"Erro ao ler arquivo: {str(e)}"], [], is_today=False)


def validate_meta_file(file_path: str) -> dict:
    """Valida arquivo de meta aceitando 3 ou 4 colunas.

    Formatos aceitos por linha:
    - 4 colunas: tipo;data;ciclo;valor
    - 3 colunas: tipo;data;valor (assume ciclo='')

    Consolidação (para retorno único por indicador):
    - Para PEF/EUD: escolhe o maior ciclo numérico do dia; se não houver ciclo numérico, usa ciclo vazio ('') do dia.
    - Para LOJA: ignora ciclo; usa a última linha do dia.
    """
    import csv
    from datetime import datetime

    # Inicializa o resultado com todos os indicadores
    result = {
        'PEF': {'is_valid': False, 'data': None, 'valor': None},
        'EUD': {'is_valid': False, 'data': None, 'valor': None},
        'LOJA': {'is_valid': False, 'data': None, 'valor': None}
    }

    today = datetime.today().date()

    # Coletores por indicador
    pef_entries = []  # (data_str, ciclo_str, valor)
    eud_entries = []
    loja_entries = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')

            for row in reader:
                if not row:
                    continue
                # Normaliza para 4 colunas
                if len(row) == 4:
                    tipo, data_str, ciclo_str, valor_str = row
                elif len(row) == 3:
                    tipo, data_str, valor_str = row
                    ciclo_str = ''
                else:
                    # Formato inesperado
                    continue

                tipo = (tipo or '').strip().upper()
                if tipo == 'EUDORA':
                    tipo = 'EUD'

                # Só processa tipos esperados
                if tipo not in ['PEF', 'EUD', 'LOJA']:
                    continue

                try:
                    data_meta = datetime.strptime(data_str.strip(), "%d/%m/%Y").date()
                except Exception:
                    continue

                if data_meta != today:
                    continue

                try:
                    valor = float(str(valor_str).strip())
                except Exception:
                    continue

                if tipo == 'PEF':
                    pef_entries.append((data_str.strip(), (ciclo_str or '').strip(), valor))
                elif tipo == 'EUD':
                    eud_entries.append((data_str.strip(), (ciclo_str or '').strip(), valor))
                elif tipo == 'LOJA':
                    loja_entries.append((data_str.strip(), (ciclo_str or '').strip(), valor))

        # Consolida PEF/EUD: maior ciclo numérico do dia; senão ciclo vazio
        def pick_consolidated(entries):
            if not entries:
                return None
            # Se houver algum com ciclo numérico, escolher o maior
            numeric = []
            empty = []
            for data_str, ciclo_str, valor in entries:
                if ciclo_str.isdigit():
                    try:
                        numeric.append((int(ciclo_str), data_str, valor))
                    except Exception:
                        pass
                else:
                    empty.append((data_str, valor))
            if numeric:
                ciclo_max, data_str, valor = max(numeric, key=lambda x: x[0])
                return data_str, valor
            if empty:
                data_str, valor = empty[-1]  # última ocorrência do dia sem ciclo
                return data_str, valor
            return None

        pef_pick = pick_consolidated(pef_entries)
        if pef_pick:
            data_str, valor = pef_pick
            result['PEF'] = {
                'is_valid': True,
                'data': data_str,
                'valor': valor
            }

        eud_pick = pick_consolidated(eud_entries)
        if eud_pick:
            data_str, valor = eud_pick
            result['EUD'] = {
                'is_valid': True,
                'data': data_str,
                'valor': valor
            }

        # LOJA: usa a última ocorrência do dia (ignora ciclo)
        if loja_entries:
            data_str, _ciclo, valor = loja_entries[-1]
            result['LOJA'] = {
                'is_valid': True,
                'data': data_str,
                'valor': valor
            }

        return result

    except FileNotFoundError:
        return result
    except Exception as e:
        import logging
        logging.error(f"Erro ao validar arquivo de metas: {str(e)}")
        return {k: {'is_valid': False, 'data': None, 'valor': None, 'error': str(e)} for k in result}
