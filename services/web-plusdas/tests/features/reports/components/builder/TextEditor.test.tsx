// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { ReportBlock } from '@/api/types/reports';
import { TextEditor } from '@/features/reports/components/builder/TextEditor';
import type { BuilderOptions } from '@/features/reports/types';

type TextBlock = Extract<ReportBlock, { kind: 'text' }>;

const OPTIONS: BuilderOptions = {
  points: [],
  devices: [{ deviceId: 12, deviceName: 'gen_1', deviceType: 'GENERATOR' }] as DevicePointsEntry[],
  functions: [],
  textVariables: {
    site: [{ name: 'site_name', description: 'Site name' }],
    device_fields: [{ name: 'name', description: 'Name' }, { name: 'type', description: 'Type' }],
    point_fields: [{ name: 'name', description: 'Name' }],
  },
  siteName: 'Alpha Solar Farm',
  timeZone: 'UTC',
};

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {}; // Radix Select scrolls the chosen option into view
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
});

function renderEditor(body: string) {
  const onChange = vi.fn();
  const block: TextBlock = { kind: 'text', id: 'text_1', body };
  render(<TextEditor block={block} options={OPTIONS} onChange={onChange} />);
  return onChange;
}

async function choose(selectName: string, optionName: string) {
  fireEvent.keyDown(screen.getByRole('combobox', { name: selectName }), { key: 'Enter' });
  fireEvent.click(await screen.findByRole('option', { name: optionName }));
}

describe('TextEditor', () => {
  it('inserts a device variable where the cursor is', async () => {
    const onChange = renderEditor('In the event  explodes');
    const textArea = screen.getByLabelText('Text') as HTMLTextAreaElement;
    textArea.setSelectionRange(13, 13);
    await choose('Device', 'gen_1');
    fireEvent.click(screen.getAllByRole('button', { name: 'Insert' })[1]);
    expect(onChange).toHaveBeenLastCalledWith({ kind: 'text', id: 'text_1', body: 'In the event {device:12.name} explodes' });
  });

  it('inserts a site variable', async () => {
    const onChange = renderEditor('');
    await choose('Site variable', 'Site name');
    fireEvent.click(screen.getAllByRole('button', { name: 'Insert' })[0]);
    expect(onChange).toHaveBeenLastCalledWith({ kind: 'text', id: 'text_1', body: '{site_name}' });
  });

  it('can insert only once something is chosen', () => {
    renderEditor('x');
    for (const button of screen.getAllByRole('button', { name: 'Insert' })) expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it('previews the text with names filled in', () => {
    renderEditor('In the event {device:12.name} explodes at {site_name}');
    expect(screen.getByLabelText('text_1 preview').textContent).toBe('In the event gen_1 explodes at Alpha Solar Farm');
  });
});
