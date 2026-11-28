"""Funções de IA do DentFlow (Claude via Agno).

Inspirado no workshop Arcane 4 (PetCare), adaptado ao consultório odontológico:
triagem de urgência, leitura de anexos, resumo do prontuário, chat com o prontuário
e secretária que marca na agenda do próprio DentFlow.

Regra de ouro: a IA sugere, o dentista decide. Nenhuma função altera o prontuário sozinha
(a secretária só marca consulta, com a mesma validação de horário da agenda).
"""
