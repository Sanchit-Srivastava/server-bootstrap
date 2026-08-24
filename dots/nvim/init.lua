-- Small, dependency-free Neovim configuration for remote administration.
vim.g.mapleader = " "
vim.g.maplocalleader = " "

vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.mouse = "a"
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.splitbelow = true
vim.opt.splitright = true
vim.opt.termguicolors = true
vim.opt.signcolumn = "yes"
vim.opt.updatetime = 250
vim.opt.timeoutlen = 400
vim.opt.undofile = true
vim.opt.clipboard = "unnamedplus"

vim.keymap.set("n", "<leader>w", "<cmd>write<cr>", { desc = "Write file" })
vim.keymap.set("n", "<leader>q", "<cmd>quit<cr>", { desc = "Quit" })
vim.keymap.set("n", "<C-h>", "<C-w>h", { desc = "Focus left" })
vim.keymap.set("n", "<C-j>", "<C-w>j", { desc = "Focus below" })
vim.keymap.set("n", "<C-k>", "<C-w>k", { desc = "Focus above" })
vim.keymap.set("n", "<C-l>", "<C-w>l", { desc = "Focus right" })
vim.keymap.set("n", "<leader>e", "<cmd>Explore<cr>", { desc = "File explorer" })
vim.keymap.set("n", "<Esc>", "<cmd>nohlsearch<cr>")

vim.api.nvim_create_autocmd("TextYankPost", {
  desc = "Highlight text after yanking",
  callback = function()
    vim.highlight.on_yank()
  end,
})
