---
status: aceita
data: 2026-10-30
---

# Fazer o autoencoder com o MLPRegressor do scikit-learn, não com PyTorch

O autoencoder é um `MLPRegressor` treinado para reconstruir a própria entrada
(`nids.models.anomaly.Autoencoder`), e o erro quadrático médio da reconstrução é o score de anomalia.
Com 59 atributos e uma rede de poucas camadas, o scikit-learn basta. O modelo vira um joblib como os
outros e a API pode servi-lo sem ONNX e sem uma dependência de cerca de 200 MB.

## Opções consideradas

- **PyTorch (CPU), como previa a arquitetura:** controle total sobre a rede, a perda e o treino, mas
  exigiria exportar para ONNX para servir na API, e nada no problema pede isso.

## Consequências

- Não há GPU, regularização por camada nem funções de perda próprias. Se o autoencoder precisar
  disso para competir, a decisão volta a ser discutida.
- A parada antecipada (`early_stopping`) separa 10 % do treino ao acaso e mede o R² da reconstrução,
  não o erro nos fluxos normais da validação do P2.
