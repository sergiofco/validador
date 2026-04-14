// ==UserScript==
// @name         Validador de Mensuradores
// @namespace    https://github.com/sergiofco
// @version      1.5.0
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

    function lerTotal(section) {
        const txt = section.querySelector('span.totalizador-total-total')?.textContent.trim() || '0';
        return parseInt(txt.replace(/\D/g, ''), 10) || 0;
    }

    function getSecaoPorTitulo(titulo) {
        return Array.from(document.querySelectorAll('section.mensuradores-section'))
            .find(s => s.querySelector('h5')?.textContent.trim() === titulo) || null;
    }

    /**
     * Retorna lista de candidatos de identificação, do mais específico ao menos:
     * [realizacao, modalidade, atividade]
     * O motor tenta cada um até encontrar uma chave em VALIDACOES.
     */
    function getCandidatos() {
        const candidatos = [];

        const breadcrumb = document.querySelector('span[ng-bind*="vm.sessao.modalidade"]')?.textContent.trim();
        if (breadcrumb) {
            const partes = breadcrumb.split('>>').map(p => p.trim()).filter(Boolean);
            // partes[2] = modalidade, partes[1] = atividade — testados antes da realizacao
            if (partes[2]) candidatos.push(partes[2]);
            if (partes[1]) candidatos.push(partes[1]);
        }

        const realizacao = document.querySelector('span[ng-bind="vm.sessao.realizacao"]')?.textContent.trim();
        if (realizacao) candidatos.push(realizacao);

        console.log('[Validador] candidatos:', candidatos);
        return candidatos;
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

        erros.push(...validarPresencasNaoZero());
        return erros;
    };

    // Competições físico-esportivas: ao menos um campo de "Partidas / Provas" deve ser > 0
    VALIDACOES['Competições físico-esportivas'] = function () {
        const erros = [];
        const norm = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

        const todasLinhas = Array.from(document.querySelectorAll('tr'));
        console.log('[Validador] Competições: total de <tr>:', todasLinhas.length);
        console.log('[Validador] Competições: títulos encontrados:',
            todasLinhas.map(tr => tr.querySelector('span[ng-bind="line.title"]')?.textContent.trim()).filter(Boolean)
        );

        const linhaPartidas = todasLinhas.find(tr =>
            norm(tr.querySelector('span[ng-bind="line.title"]')?.textContent.trim() || '') === norm('Partidas / Provas')
        );

        if (!linhaPartidas) {
            erros.push('• Linha "Partidas / Provas" não encontrada na página');
            return erros;
        }

        const inputs = Array.from(linhaPartidas.querySelectorAll('input[ui-number-mask]'));
        console.log('[Validador] Competições: inputs em Partidas/Provas:', inputs.length, inputs.map(i => JSON.stringify(i.value)));
        const algumPreenchido = inputs.some(inp => parseValor(inp) > 0);

        if (!algumPreenchido) {
            erros.push('• Partidas / Provas: ao menos uma coluna deve ser maior que zero');
        }

        erros.push(...validarPresencasNaoZero());
        return erros;
    };

    // Viagens / Passeios: Total de Inscritos no dia == Total de Procedência dos inscritos
    function validarTotalInscritos() {
        const erros = [];

        const inscritosSection   = getSecaoPorTitulo('Inscritos no dia');
        const procedenciaSection = getSecaoPorTitulo('Procedência dos inscritos');

        if (!inscritosSection || !procedenciaSection) return erros;

        const totalInscritos   = lerTotal(inscritosSection);
        const totalProcedencia = lerTotal(procedenciaSection);

        if (totalInscritos !== totalProcedencia) {
            erros.push(
                `• Total de Inscritos no dia (${totalInscritos}) ≠ ` +
                `Total de Procedência dos inscritos (${totalProcedencia})`
            );
        }

        erros.push(...validarPresencasNaoZero());
        return erros;
    }

    // Regra compartilhada: inscritos > 0 com presenças zeradas
    function validarPresencasNaoZero() {
        const erros = [];
        const inscritosSection = getSecaoPorTitulo('Inscritos no dia');
        const presencasSection = getSecaoPorTitulo('Presenças');
        if (!inscritosSection || !presencasSection) return erros;

        const totalInscritos = lerTotal(inscritosSection);
        const totalPresencas = lerTotal(presencasSection);

        if (totalInscritos > 0 && totalPresencas === 0) {
            erros.push(`• Presenças zeradas com ${totalInscritos} inscrito(s) no dia`);
        }
        return erros;
    }

    VALIDACOES['Viagens']  = validarTotalInscritos;
    VALIDACOES['Passeios'] = validarTotalInscritos;

    // Intervenção urbana: único campo em tela deve ser exatamente 1
    VALIDACOES['Intervenção urbana'] = function () {
        const erros = [];

        const inputs = Array.from(document.querySelectorAll('tabela-mensuradores input[ui-number-mask]'));

        if (inputs.length === 0) {
            erros.push('• Nenhum campo de mensurador encontrado na página');
            return erros;
        }

        const valor = parseValor(inputs[0]);

        if (valor !== 1) {
            erros.push(`• O campo deve ser exatamente 1 (valor informado: ${valor})`);
        }

        return erros;
    };

    // ─── Motor de validação ──────────────────────────────────────────────────────

    function validar() {
        const candidatos = getCandidatos();
        if (candidatos.length === 0) return true;

        const norm = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
        const chaves = Object.keys(VALIDACOES);
        console.log('[Validador] chaves registradas:', chaves);

        let chave = null;
        let candidatoUsado = null;
        for (const c of candidatos) {
            chave = chaves.find(k => norm(k) === norm(c)) ?? null;
            if (chave) { candidatoUsado = c; break; }
        }
        console.log('[Validador] chave matched:', chave ?? '(nenhuma)', '← candidato:', candidatoUsado);

        if (!chave) return true;

        const erros = VALIDACOES[chave]();

        if (erros.length > 0) {
            alert(
                `Validação de Mensuradores [${chave}] — erro encontrado:\n\n` +
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
