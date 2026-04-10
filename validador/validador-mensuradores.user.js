// ==UserScript==
// @name         Validador de Mensuradores
// @namespace    https://github.com/sergiofco
// @version      1.2.0
// @description  Valida lançamento de mensuradores antes de salvar, por tipo de realização
// @author       sergiofco
// @include      /^https?:\/\/webapps\.[^/]+\.sescsp\.org\.br\/estatistico\//
// @updateURL    https://raw.githubusercontent.com/sergiofco/validador/main/validador/validador-mensuradores.user.js
// @downloadURL  https://raw.githubusercontent.com/sergiofco/validador/main/validador/validador-mensuradores.user.js
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    // ─── Utilitários ────────────────────────────────────────────────────────────

    const COLUNAS = [
        'Pleno - Titular',
        'Pleno - Dependente',
        'MIS e Atividade',
        'Não identificado'
    ];

    function parseValor(input) {
        const raw = input.value.replace(/\D/g, '');
        return raw === '' ? 0 : parseInt(raw, 10);
    }

    function getLinhas(section) {
        return Array.from(section.querySelectorAll('tbody tr')).map(tr => {
            const nome = tr.querySelector('span[ng-bind="line.title"]')?.textContent.trim() || '';
            const inputs = Array.from(tr.querySelectorAll('input[ui-number-mask]'));
            return { nome, inputs };
        });
    }

    function getSecaoPorTitulo(titulo) {
        return Array.from(document.querySelectorAll('section.mensuradores-section'))
            .find(s => s.querySelector('h5')?.textContent.trim() === titulo) || null;
    }

    function getRealizacao() {
        return document.querySelector('span[ng-bind="vm.sessao.realizacao"]')?.textContent.trim() || null;
    }

    // ─── Validações por tipo de realização ──────────────────────────────────────

    /**
     * Registro de validações: cada chave é um valor de vm.sessao.realizacao.
     * O valor é uma função que retorna um array de strings de erro (vazio = válido).
     *
     * Para adicionar uma nova validação:
     *   VALIDACOES['NomeDoTipo'] = function() { return []; }
     */
    const VALIDACOES = {};

    // Oficina: Presenças <= Inscritos no dia, célula a célula
    VALIDACOES['Oficina'] = function () {
        const erros = [];

        const inscritosSection = getSecaoPorTitulo('Inscritos no dia');
        const presencasSection = getSecaoPorTitulo('Presenças');

        if (!inscritosSection || !presencasSection) return erros;

        const inscritosLinhas = getLinhas(inscritosSection);
        const presencasLinhas = getLinhas(presencasSection);

        inscritosLinhas.forEach((inscLinha, linhaIdx) => {
            const presLinha = presencasLinhas[linhaIdx];
            if (!presLinha) return;

            inscLinha.inputs.forEach((inscInput, colIdx) => {
                const presInput = presLinha.inputs[colIdx];
                if (!presInput) return;

                const inscVal = parseValor(inscInput);
                const presVal = parseValor(presInput);

                if (presVal > inscVal) {
                    const coluna = COLUNAS[colIdx] || `Coluna ${colIdx + 1}`;
                    erros.push(`• ${presLinha.nome} / ${coluna}: Presenças (${presVal}) > Inscritos no dia (${inscVal})`);
                }
            });
        });

        return erros;
    };

    // Intervenção urbana: único campo em tela deve ser exatamente 1
    VALIDACOES['Intervenção urbana'] = function () {
        const erros = [];

        const inputs = Array.from(document.querySelectorAll('tabela-mensuradores input[ui-number-mask]'));

        if (inputs.length === 0) return erros;

        const valor = parseValor(inputs[0]);

        if (valor !== 1) {
            erros.push(`• O campo deve ser exatamente 1 (valor informado: ${valor})`);
        }

        return erros;
    };

    // ─── Motor de validação ──────────────────────────────────────────────────────

    function validar() {
        const realizacao = getRealizacao();

        if (!realizacao || !VALIDACOES[realizacao]) return true;

        const erros = VALIDACOES[realizacao]();

        if (erros.length > 0) {
            alert(
                `Validação de Mensuradores [${realizacao}] — erro encontrado:\n\n` +
                erros.join('\n') +
                '\n\nO registro não foi salvo. Corrija os valores e tente novamente.'
            );
            return false;
        }

        return true;
    }

    // ─── Inicialização ───────────────────────────────────────────────────────────

    function ativar() {
        document.addEventListener('click', function (e) {
            const btn = e.target.closest('button.btn-secondary');
            if (!btn) return;
            if (!document.querySelector('tabela-mensuradores')) return;

            if (!validar()) {
                e.stopImmediatePropagation();
                e.preventDefault();
            }
        }, true);
    }

    function aguardarComponente() {
        if (document.querySelector('tabela-mensuradores')) {
            ativar();
            return;
        }

        const observer = new MutationObserver((_, obs) => {
            if (document.querySelector('tabela-mensuradores')) {
                obs.disconnect();
                ativar();
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', aguardarComponente);
    } else {
        aguardarComponente();
    }

})();
