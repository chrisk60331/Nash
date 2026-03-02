const {
  getPresetBB,
  getPresetsBB,
  savePresetBB,
  deletePresetsBB,
} = require('@librechat/api');

module.exports = {
  getPreset: getPresetBB,
  getPresets: getPresetsBB,
  savePreset: savePresetBB,
  deletePresets: deletePresetsBB,
};
