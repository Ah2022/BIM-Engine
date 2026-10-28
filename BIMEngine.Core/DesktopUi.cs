using System;
using System.Collections.Generic;
using System.Drawing;
using System.Threading;
using System.Windows.Forms;

namespace BIMEngine.Core
{
    public sealed class WindowOwner : IWin32Window
    {
        public IntPtr Handle { get; private set; }
        public WindowOwner(long handle) { Handle = new IntPtr(handle); }
    }
    public static class DesktopUi
    {
        public static int ShowReport(long owner, string summary, string[] columns, string[][] rows)
        {
            using (var form = new Form { Text = "BIM Engine - Issue Report", Width = 1220, Height = 680,
                StartPosition = FormStartPosition.CenterParent })
            {
                var label = new Label { Text = summary, Dock = DockStyle.Top, Height = 100, Padding = new Padding(8) };
                var grid = new DataGridView { Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false,
                    AllowUserToDeleteRows = false, MultiSelect = false, SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                    AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.DisplayedCells };
                foreach (var column in columns) grid.Columns.Add(column, column);
                for (int i = 0; i < rows.Length; i++)
                {
                    int index = grid.Rows.Add(rows[i]);
                    grid.Rows[index].Tag = i;
                }
                var footer = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 42 };
                var select = new Button { Text = "Select host elements", Width = 170, Height = 32 };
                var close = new Button { Text = "Close", Width = 100, Height = 32, DialogResult = DialogResult.Cancel };
                select.Click += (s,e) => { if (grid.CurrentRow != null) form.DialogResult = DialogResult.OK; };
                footer.Controls.Add(select); footer.Controls.Add(close);
                form.Controls.Add(grid); form.Controls.Add(label); form.Controls.Add(footer);
                form.CancelButton = close;
                return form.ShowDialog(new WindowOwner(owner)) == DialogResult.OK ? (int)grid.CurrentRow.Tag : -1;
            }
        }

        public static void Alert(long owner, string message)
        { MessageBox.Show(new WindowOwner(owner), message, "BIM Engine", MessageBoxButtons.OK, MessageBoxIcon.Information); }

        public static string[] ChooseCategories(long owner, string[] choices, string[] selected)
        {
            using (var form = new Form { Text = "BIM Engine - Categories", Width = 440, Height = 400,
                StartPosition = FormStartPosition.CenterParent, MinimizeBox = false, MaximizeBox = false })
            {
                var list = new CheckedListBox { Dock = DockStyle.Fill, CheckOnClick = true };
                foreach (var item in choices) list.Items.Add(item, Array.IndexOf(selected, item) >= 0);
                var save = new Button { Text = "Save Categories", Dock = DockStyle.Bottom, Height = 40 };
                save.Click += (s,e) => { if (list.CheckedItems.Count == 0) return; form.DialogResult = DialogResult.OK; };
                form.Controls.Add(list); form.Controls.Add(save); form.AcceptButton = save;
                if (form.ShowDialog(new WindowOwner(owner)) != DialogResult.OK) return null;
                var result = new List<string>();
                foreach (var item in list.CheckedItems) result.Add((string)item);
                return result.ToArray();
            }
        }
    }

    // Dedicated UI thread: no Revit API calls or Revit event pumping here.
    // A timer reads immutable progress snapshots; Cancel only sets a flag.
    public sealed class ScanProgressWindow : IDisposable
    {
        private volatile bool _cancelled, _closed;
        private volatile string _stage = "Initializing";
        private int _current, _total;
        private readonly Thread _thread;
        public bool Cancelled => _cancelled;
        public ScanProgressWindow(long owner)
        {
            _thread = new Thread(() =>
            {
                using (var form = new Form { Text = "BIM Engine - Scan", Width = 460, Height = 160,
                    StartPosition = FormStartPosition.CenterScreen, MinimizeBox = false, MaximizeBox = false })
                using (var timer = new System.Windows.Forms.Timer { Interval = 100 })
                {
                    var label = new Label { Dock = DockStyle.Top, Height = 30, Text = _stage };
                    var bar = new ProgressBar { Dock = DockStyle.Top, Height = 25 };
                    var cancel = new Button { Text = "Cancel", Dock = DockStyle.Bottom, Height = 32 };
                    cancel.Click += (s,e) => { _cancelled = true; cancel.Enabled = false; };
                    form.FormClosing += (s,e) => { if (!_closed) _cancelled = true; };
                    form.Controls.Add(bar); form.Controls.Add(label); form.Controls.Add(cancel);
                    timer.Tick += (s,e) =>
                    {
                        if (_closed) { form.Close(); return; }
                        label.Text = _stage + "  " + _current + (_total > 0 ? "/" + _total : "");
                        bar.Style = _total > 0 ? ProgressBarStyle.Continuous : ProgressBarStyle.Marquee;
                        if (_total > 0) bar.Value = Math.Min(100, (int)(100.0 * _current / _total));
                    };
                    timer.Start();
                    form.ShowDialog(new WindowOwner(owner));
                }
            });
            _thread.IsBackground = true;
            _thread.SetApartmentState(ApartmentState.STA);
            _thread.Start();
        }
        public void Update(string stage, int current, int total)
        {
            if (_cancelled) throw new OperationCanceledException("Scan cancelled. No results saved.");
            _stage = stage; _current = current; _total = total;
        }
        public void Dispose() { _closed = true; _thread.Join(2000); }
    }
}
