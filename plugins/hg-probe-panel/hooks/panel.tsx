// hg-probe panel: the smallest pane beside the chat, one fixed line.
// It is its own plugin, apart from hg-probe, so a surface that refuses a module tells nothing about plugins in general.
// It also leaves .hg-probe-panel in the working folder, so the hg-probe skill can report what was observed:
// that the module loaded, what $.ui.open answered, and on which surface the pane was drawn.
import type { EngineInterface, Register } from 'claude-code'

const PANE = 'hg-probe'
const MARKER = '.hg-probe-panel'

const seen = { opened: 'not answered yet', drawnOn: 'not drawn yet' }

async function save($: EngineInterface): Promise<void> {
  const text = [
    'hg-probe panel module loaded',
    `ui.open: ${seen.opened}`,
    `drawn on surface: ${seen.drawnOn}`,
    '',
  ].join('\n')
  try {
    await $.fs.write(MARKER, text)
  } catch {
    // The folder may refuse a write; the skill then reports that no marker was found.
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await save($)
    void $.ui.open({ id: PANE, title: 'hg-probe' }).then(
      async result => {
        seen.opened = result.isPlaced ? 'isPlaced true' : `isPlaced false, reason: ${result.reason}`
        await save($)
      },
      async error => {
        seen.opened = `rejected: ${String(error)}`
        await save($)
      },
    )

    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Text } = $.ui.resolve(e)
    if (seen.drawnOn !== e.surface) {
      seen.drawnOn = e.surface
      await save($)
    }

    return <Text>hg-probe: panel działa</Text>
  })
}
