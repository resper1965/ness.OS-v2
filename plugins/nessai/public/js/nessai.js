/**
 * -------------------------------------------------------------------------
 * nessai - GLPI Plugin
 * Copyright (C) 2024-2026 ness. (https://ness.com.br)
 * -------------------------------------------------------------------------
 *
 * Frontend controller for the nessai AI assistant.
 * Injects action buttons into GLPI 11 ticket forms and communicates
 * with the plugin AJAX backend.
 *
 * @package   nessai
 * @author    ness.
 * @copyright 2024-2026 ness.
 * @license   GPLv3+
 */

$(document).ready(function () {
   'use strict';

   // -----------------------------------------------------------------------
   // 1. Gate: only run on existing-ticket form pages
   // -----------------------------------------------------------------------
   var href = window.location.href;
   if (href.indexOf('ticket.form.php') === -1) {
      return;
   }

   var ticketId = _nessaiGetTicketId();
   if (!ticketId) {
      return; // new-ticket page — nothing to do
   }

   // -----------------------------------------------------------------------
   // 2. Resolve GLPI root_doc
   // -----------------------------------------------------------------------
   var rootDoc = _nessaiGetRootDoc();

   // -----------------------------------------------------------------------
   // 3. Build the toolbar
   // -----------------------------------------------------------------------
   var $toolbar = $(
      '<div class="nessai-toolbar" id="nessai-toolbar">' +
         '<button type="button" class="btn nessai-btn-suggest" data-nessai-action="suggest">' +
            '✨ Sugerir Resposta' +
         '</button>' +
         '<button type="button" class="btn nessai-btn-summarize" data-nessai-action="summarize">' +
            '📋 Resumir Timeline' +
         '</button>' +
         '<button type="button" class="btn nessai-btn-translate" data-nessai-action="translate">' +
            '🌐 Traduzir (EN)' +
         '</button>' +
         '<span class="nessai-branding">powered by ness<span class="nessai-brand-dot">.</span> AI</span>' +
      '</div>'
   );

   _nessaiInjectToolbar($toolbar);

   // -----------------------------------------------------------------------
   // 4. Debounce helper
   // -----------------------------------------------------------------------
   var _lastClickTs = 0;
   var DEBOUNCE_MS  = 300;

   // -----------------------------------------------------------------------
   // 5. Button click handler
   // -----------------------------------------------------------------------
   $toolbar.on('click', '[data-nessai-action]', function (e) {
      e.preventDefault();

      var now = Date.now();
      if (now - _lastClickTs < DEBOUNCE_MS) {
         return;
      }
      _lastClickTs = now;

      var $btn       = $(this);
      var action     = $btn.data('nessai-action');
      var csrfToken  = _nessaiGetCsrf();
      var origLabel  = $btn.html();

      // Show spinner & disable
      $btn.html('<span class="nessai-spinner"></span>').prop('disabled', true);

      $.ajax({
         url:      rootDoc + '/plugins/nessai/front/ajax.php',
         type:     'POST',
         dataType: 'json',
         headers:  { 'X-Glpi-Csrf-Token': csrfToken },
         data: {
            ticket_id:          ticketId,
            action:             action,
            _glpi_csrf_token:   csrfToken
         },
         success: function (response) {
            var text = (typeof response === 'object' && response !== null)
               ? (response.content || response.data || response.message || JSON.stringify(response))
               : String(response);

            switch (action) {
               case 'suggest':
                  _nessaiInsertSuggestion(text);
                  break;
               case 'summarize':
                  _nessaiShowModal('📋 Resumo da Timeline', text);
                  break;
               case 'translate':
                  _nessaiShowModal('🌐 Tradução (EN)', text);
                  break;
            }
         },
         error: function (xhr) {
            var msg = 'Erro ao comunicar com a API nessai.';
            try {
               var body = JSON.parse(xhr.responseText);
               if (body && body.error) {
                  msg = body.error;
               }
            } catch (_e) { /* ignore */ }

            _nessaiShowAlert(msg);
         },
         complete: function () {
            $btn.html(origLabel).prop('disabled', false);
         }
      });
   });

   // =====================================================================
   // Internal helpers
   // =====================================================================

   /**
    * Extract ticket ID from the URL (?id=NNN) or from a hidden form input.
    * Returns the numeric ID or null if this is a new-ticket page.
    */
   function _nessaiGetTicketId() {
      // Try URL param "id"
      var match = href.match(/[?&]id=(\d+)/);
      if (match) {
         return parseInt(match[1], 10);
      }

      // Try URL param "tickets_id"
      match = href.match(/[?&]tickets_id=(\d+)/);
      if (match) {
         return parseInt(match[1], 10);
      }

      // Try hidden inputs
      var $input = $('input[name="id"]').filter(function () {
         return $(this).val() && parseInt($(this).val(), 10) > 0;
      });
      if ($input.length) {
         return parseInt($input.first().val(), 10);
      }

      $input = $('input[name="tickets_id"]');
      if ($input.length && parseInt($input.val(), 10) > 0) {
         return parseInt($input.val(), 10);
      }

      return null;
   }

   /**
    * Resolve the GLPI root_doc path.
    */
   function _nessaiGetRootDoc() {
      // Prefer the global JS config object
      if (typeof CFG_GLPI !== 'undefined' && CFG_GLPI.root_doc) {
         return CFG_GLPI.root_doc;
      }

      // Fallback: derive from current URL
      var pathParts = window.location.pathname.split('/front/');
      if (pathParts.length > 1) {
         return pathParts[0];
      }

      return '';
   }

   /**
    * Get the CSRF token from the page.
    */
   function _nessaiGetCsrf() {
      var token = $('input[name=_glpi_csrf_token]').val();
      if (token) {
         return token;
      }

      token = $('meta[name="glpi:csrf_token"]').attr('content');
      if (token) {
         return token;
      }

      return '';
   }

   /**
    * Inject the toolbar into the best available anchor point.
    */
   function _nessaiInjectToolbar($el) {
      // 1st: GLPI 11 timeline answer area
      var $timelineButtons = $('.timeline-buttons');
      if ($timelineButtons.length) {
         $timelineButtons.first().before($el);
         return;
      }

      // 2nd: after the timeline itself
      var $timeline = $('.itil-timeline');
      if ($timeline.length) {
         $timeline.first().after($el);
         return;
      }

      // 3rd: before the new-object form
      var $newForm = $('#new-itilobject-form');
      if ($newForm.length) {
         $newForm.before($el);
         return;
      }

      // Fallback: top of main tab content
      var $tabContent = $('.tab-content.main_form, .tab-content');
      if ($tabContent.length) {
         $tabContent.first().prepend($el);
         return;
      }

      // Last resort
      $('body').append($el);
   }

   /**
    * Insert AI-suggested text into the TinyMCE editor or raw textarea.
    */
   function _nessaiInsertSuggestion(text) {
      // TinyMCE (GLPI 11 uses TinyMCE for follow-ups)
      if (typeof tinymce !== 'undefined' && tinymce.activeEditor) {
         tinymce.activeEditor.setContent(text);
         return;
      }

      // Fallback: direct textarea
      var $ta = $('textarea[name="content"]');
      if (!$ta.length) {
         $ta = $('#content');
      }
      if ($ta.length) {
         $ta.val(text).trigger('change');
      }
   }

   /**
    * Display a Tabler-styled modal with content and a copy button.
    */
   function _nessaiShowModal(title, body) {
      // Remove any existing modal
      $('#nessai-modal-overlay').remove();

      var $overlay = $(
         '<div class="nessai-modal-overlay" id="nessai-modal-overlay">' +
            '<div class="nessai-modal">' +
               '<div class="nessai-modal-header">' +
                  '<span class="nessai-modal-title">' + _escHtml(title) + '</span>' +
                  '<button type="button" class="nessai-modal-close" title="Fechar">&times;</button>' +
               '</div>' +
               '<div class="nessai-modal-body"></div>' +
               '<div class="nessai-modal-footer">' +
                  '<button type="button" class="btn nessai-copy-btn">📋 Copiar</button>' +
               '</div>' +
            '</div>' +
         '</div>'
      );

      // Set body text safely
      $overlay.find('.nessai-modal-body').text(body);

      // Close
      $overlay.find('.nessai-modal-close').on('click', function () {
         $overlay.remove();
      });
      $overlay.on('click', function (ev) {
         if ($(ev.target).hasClass('nessai-modal-overlay')) {
            $overlay.remove();
         }
      });

      // Copy
      $overlay.find('.nessai-copy-btn').on('click', function () {
         var $self = $(this);
         if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(body).then(function () {
               $self.text('✅ Copiado!');
               setTimeout(function () { $self.text('📋 Copiar'); }, 1500);
            });
         } else {
            // Fallback
            var $tmp = $('<textarea>').val(body).appendTo('body').select();
            document.execCommand('copy');
            $tmp.remove();
            $self.text('✅ Copiado!');
            setTimeout(function () { $self.text('📋 Copiar'); }, 1500);
         }
      });

      $('body').append($overlay);
   }

   /**
    * Show a dismissible Tabler-style alert at the top of the toolbar.
    */
   function _nessaiShowAlert(message) {
      var $alert = $(
         '<div class="nessai-alert alert alert-danger alert-dismissible" role="alert">' +
            '<div class="d-flex">' +
               '<div>' + _escHtml(message) + '</div>' +
            '</div>' +
            '<a class="btn-close" data-bs-dismiss="alert" aria-label="Close"></a>' +
         '</div>'
      );

      var $toolbar = $('#nessai-toolbar');
      if ($toolbar.length) {
         $toolbar.before($alert);
      } else {
         $('body').prepend($alert);
      }

      // Auto-dismiss after 6 seconds
      setTimeout(function () { $alert.fadeOut(300, function () { $(this).remove(); }); }, 6000);
   }

   /**
    * Minimal HTML escaping.
    */
   function _escHtml(str) {
      var div = document.createElement('div');
      div.appendChild(document.createTextNode(str));
      return div.innerHTML;
   }
});
