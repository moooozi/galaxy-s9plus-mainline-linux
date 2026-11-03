"""Exercise the mobile prompt's input clearing without losing a PAM question."""
from pathlib import Path
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[3]


class MobileAuthPromptTests(unittest.TestCase):
    def test_hiding_prompt_preserves_question_and_erases_input(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is required for the Shell authentication test')
        patch = (REPO / 'image/gnome-mobile/patches/gnome-shell/'
                 '0004-preserve-hidden-auth-question.patch').read_text()
        additions = '\n'.join(line[1:] for line in patch.splitlines()
                              if line.startswith('+') and not line.startswith('+++'))
        method = additions.split('    clearInput() {', 1)[1].split('\n    }', 1)[0]
        program = '''
const assert = require('node:assert/strict');
const AuthPromptStatus = {VERIFYING: 1, VERIFICATION_IN_PROGRESS: 5};
const answerHandler = () => {};
const prompt = {
    verificationStatus: AuthPromptStatus.VERIFYING,
    _entry: {text: 'typed secret', visible: true, reactive: true},
    _inactiveEntry: {text: 'other secret'},
    _queryingService: 'gdm-password',
    _pendingCallback: answerHandler,
    _preemptiveAnswer: 'queued secret',
    _preemptiveInput: true,
    _clearPreemptiveState() {
        this._preemptiveInput = false;
        this._preemptiveAnswer = null;
    },
    clearInput() { METHOD
    },
};
prompt.clearInput();
assert.equal(prompt._entry.text, '');
assert.equal(prompt._inactiveEntry.text, '');
assert.equal(prompt._preemptiveAnswer, null);
assert.equal(prompt._preemptiveInput, false);
assert.equal(prompt._pendingCallback, answerHandler);
assert.equal(prompt._queryingService, 'gdm-password');
assert.equal(prompt._entry.visible, true);
assert.equal(prompt._entry.reactive, true);
prompt.clearInput(); // Repeated clock transitions preserve the same question.
assert.equal(prompt._pendingCallback, answerHandler);
prompt.verificationStatus = AuthPromptStatus.VERIFICATION_IN_PROGRESS;
prompt._entry.text = 'submitted answer';
prompt.clearInput(); // Do not disturb an answer already being processed.
assert.equal(prompt._entry.text, 'submitted answer');
'''.replace('METHOD', method)
        subprocess.run([node, '-e', program], check=True)
