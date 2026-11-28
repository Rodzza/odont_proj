"""Os agentes (equivalentes aos do workshop) com saída estruturada em Pydantic."""
from typing import Literal

from pydantic import BaseModel, Field

from . import motor

AVISO = "Você apoia um cirurgião-dentista no Brasil. Você NÃO faz diagnóstico final: sugere, e o dentista decide. Responda em português do Brasil."


# ---------- Triagem de urgência ----------


class Triagem(BaseModel):
    cor: Literal["verde", "amarelo", "laranja", "vermelho"] = Field(description="Prioridade de atendimento")
    prazo: str = Field(description="Em quanto tempo atender, ex.: 'imediato', 'hoje', 'em até 48 h', 'consulta de rotina'")
    motivo: str = Field(description="Uma ou duas frases explicando a cor")
    sinais_de_alerta: list[str] = Field(default_factory=list, description="Sinais encontrados que pesaram na decisão")
    orientacao_paciente: str = Field(description="O que dizer ao paciente até ser atendido (linguagem simples)")


CRITERIOS_TRIAGEM = """
Classifique a urgência odontológica pela cor:
- VERMELHO (imediato / pronto-socorro): inchaço que se espalha para olho, pescoço ou assoalho da boca; dificuldade para
  respirar, engolir ou abrir a boca; febre alta com inchaço facial; sangramento que não para após 15-20 min de compressão;
  trauma de face com suspeita de fratura; dente permanente avulsionado (caiu inteiro) há menos de 1 h.
- LARANJA (atender hoje): dor intensa e contínua que não melhora com analgésico; abscesso localizado com inchaço;
  dente fraturado com dor; trauma dentário recente; pericoronarite com dificuldade de abrir a boca.
- AMARELO (em até 48 h): dor moderada provocada por frio/doce que passa; restauração ou coroa que caiu com sensibilidade;
  aparelho machucando; ferida na boca há poucos dias.
- VERDE (rotina): sem dor ou dor leve ocasional; limpeza, estética, revisão, orçamento.
Considere os ALERTAS da anamnese (ex.: distúrbio de coagulação, cardiopatia, diabetes, gestante): eles podem subir a
prioridade. Na dúvida entre duas cores, escolha a mais urgente.
"""


def triagem(queixa: str, contexto_clinico: str) -> Triagem:
    return motor.rodar(
        instrucoes=[AVISO, CRITERIOS_TRIAGEM],
        mensagem=f"{contexto_clinico}\n\nQueixa relatada agora:\n{queixa}",
        rapido=True,
        esquema=Triagem,
    )


# ---------- Leitura de anexos (substitui OCR + agente de exame do workshop) ----------


class LeituraAnexo(BaseModel):
    tipo_documento: str = Field(description="Ex.: radiografia panorâmica, periapical, laudo, receita, foto intraoral")
    resumo: str = Field(description="Resumo objetivo em 2 a 4 frases")
    achados: list[str] = Field(default_factory=list, description="Achados relevantes, com dente (FDI) quando houver")
    texto_extraido: str = Field(default="", description="Texto legível do documento (vazio se for só imagem)")
    pontos_para_conferir: list[str] = Field(default_factory=list, description="O que o dentista deve confirmar no original")
    qualidade: Literal["boa", "regular", "ruim"] = Field(description="Legibilidade/qualidade da imagem")


INSTRUCOES_ANEXO = """
Leia o arquivo anexado do prontuário odontológico. Se houver texto (laudo, receita, pedido), transcreva-o em texto_extraido.
Se for imagem clínica ou radiografia, descreva os achados visíveis usando a numeração FDI quando conseguir localizar o dente,
e seja explícito sobre incertezas. Não invente achados: se a imagem não permitir avaliar algo, diga isso em pontos_para_conferir.
"""


def ler_anexo(dados: bytes, tipo: str, descricao: str | None) -> LeituraAnexo:
    from agno.media import File, Image

    imagens, arquivos = None, None
    if tipo == "application/pdf":
        arquivos = [File(content=dados, mime_type="application/pdf", filename="anexo.pdf")]
    else:
        imagens = [Image(content=dados, mime_type=tipo)]
    msg = "Leia este anexo." + (f" Descrição dada pelo dentista: {descricao}" if descricao else "")
    return motor.rodar(instrucoes=[AVISO, INSTRUCOES_ANEXO], mensagem=msg, esquema=LeituraAnexo, imagens=imagens, arquivos=arquivos)


# ---------- Resumo do prontuário ----------


class Resumo(BaseModel):
    resumo: str = Field(description="Parágrafo curto com a situação clínica atual")
    alertas: list[str] = Field(default_factory=list, description="O que o dentista precisa ver antes de atender")
    pendencias: list[str] = Field(default_factory=list, description="Tratamentos indicados ainda não feitos, com dente")
    historico: list[str] = Field(default_factory=list, description="Principais procedimentos já feitos, do mais recente ao mais antigo")
    fontes: list[str] = Field(default_factory=list, description="ids das fontes usadas, ex.: 'anamnese', 'evolucao:12'")


INSTRUCOES_RESUMO = """
Faça o resumo clínico do prontuário abaixo para o dentista ler em 30 segundos antes do atendimento.
Use SOMENTE as fontes fornecidas. Evoluções marcadas como RETIFICA corrigem a evolução citada: vale a correção.
Leituras de anexo feitas por IA são indicativas: trate-as como 'a confirmar'. Liste em `fontes` os ids que usou.
"""


def resumo(prontuario: str) -> Resumo:
    return motor.rodar(instrucoes=[AVISO, INSTRUCOES_RESUMO], mensagem=prontuario, esquema=Resumo)


# ---------- Chat com o prontuário ----------


class RespostaChat(BaseModel):
    resposta: str = Field(description="Resposta direta à pergunta")
    fontes: list[str] = Field(default_factory=list, description="ids das fontes que sustentam a resposta")
    sem_informacao: bool = Field(default=False, description="true se o prontuário não tem informação suficiente")


INSTRUCOES_CHAT = """
Responda à pergunta do dentista SOMENTE com base nas fontes do prontuário abaixo. Cite em `fontes` os ids usados.
Se as fontes não tiverem a informação, diga isso claramente e marque sem_informacao = true; não use conhecimento
externo para preencher dados do paciente. Pode usar conhecimento odontológico geral para explicar, deixando claro
o que vem do prontuário e o que é conhecimento geral.
"""


def chat(prontuario: str, historico: list[tuple[str, str]], pergunta: str) -> RespostaChat:
    conversa = "\n".join(f"{'Dentista' if quem == 'user' else 'Assistente'}: {txt}" for quem, txt in historico[-10:])
    msg = f"{prontuario}\n\n" + (f"Conversa até aqui:\n{conversa}\n\n" if conversa else "") + f"Pergunta: {pergunta}"
    return motor.rodar(instrucoes=[AVISO, INSTRUCOES_CHAT], mensagem=msg, esquema=RespostaChat)


# ---------- Busca entre pacientes (pgvector) ----------


class PacienteCitado(BaseModel):
    paciente_id: int
    motivo: str = Field(description="Por que este paciente responde à pergunta, em uma frase")
    fontes: list[str] = Field(default_factory=list, description="ids dos trechos usados, ex.: 't3'")


class RespostaBusca(BaseModel):
    resposta: str = Field(description="Resposta direta, citando os pacientes pelo primeiro nome")
    pacientes: list[PacienteCitado] = Field(default_factory=list)
    sem_informacao: bool = False


INSTRUCOES_BUSCA = """
Você recebe trechos de prontuários de VÁRIOS pacientes, encontrados por busca de significado — alguns podem não ter
relação com a pergunta. Use só os trechos que realmente respondem. Liste em `pacientes` apenas quem tem evidência
nos trechos, com os ids dos trechos usados. Se nenhum trecho responde, diga isso e marque sem_informacao = true.
Lembre que a busca pode não ter achado todos os casos: não afirme que "só estes" pacientes têm algo.
"""


def busca(pergunta: str, trechos: str) -> RespostaBusca:
    return motor.rodar(instrucoes=[AVISO, INSTRUCOES_BUSCA], mensagem=f"{trechos}\n\nPergunta: {pergunta}", esquema=RespostaBusca)
