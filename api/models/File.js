const {
  findFileByIdBB,
  getFilesBB,
  getToolFilesByIdsBB,
  getCodeGeneratedFilesBB,
  getUserCodeFilesBB,
  createFileBB,
  updateFileBB,
  updateFileUsageBB,
  deleteFileBB,
  deleteFilesBB,
  deleteFileByFilterBB,
  batchUpdateFilesBB,
} = require('@librechat/api');

module.exports = {
  findFileById: findFileByIdBB,
  getFiles: getFilesBB,
  getToolFilesByIds: getToolFilesByIdsBB,
  getCodeGeneratedFiles: getCodeGeneratedFilesBB,
  getUserCodeFiles: getUserCodeFilesBB,
  createFile: createFileBB,
  updateFile: updateFileBB,
  updateFileUsage: updateFileUsageBB,
  deleteFile: deleteFileBB,
  deleteFiles: deleteFilesBB,
  deleteFileByFilter: deleteFileByFilterBB,
  batchUpdateFiles: batchUpdateFilesBB,
};
