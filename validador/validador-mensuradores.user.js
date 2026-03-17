// ==UserScript==
// @name         Validador de Mensuradores
// @namespace    https://github.com/sergiofco
// @version      1.0.0
// @description  Valida que Presenças <= Inscritos no dia antes de salvar o registro de mensuradores
// @author       sergiofco
// @include      /^https?:\/\/webapps\.[^/]+\.sescsp\.org\.br\/estatistico\//
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

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

    function validar() {
        const sections = Array.from(document.querySelectorAll('section.mensuradores-section'));

        let inscritosSection = null;
        let presencasSection = null;

        sections.forEach(s => {
            const titulo = s.querySelector('h5')?.textContent.trim();
            if (titulo === 'Inscritos no dia') inscritosSection = s;
            if (titulo === 'Presenças') presencasSection = s;
        });

        if (!inscritosSection || !presencasSection) return true;

        const inscritosLinhas = getLinhas(inscritosSection);
        const presencasLinhas = getLinhas(presencasSection);

        const erros = [];

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

        if (erros.length > 0) {
            alert(
                'Validação de Mensuradores — erro encontrado:\n\n' +
                erros.join('\n') +
                '\n\nO registro não foi salvo. Corrija os valores e tente novamente.'
            );
            return false;
        }

        return true;
    }

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
