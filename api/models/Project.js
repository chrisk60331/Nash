const {
  getProjectByIdBB,
  getProjectByNameBB,
  addGroupIdsToProjectBB,
  removeGroupIdsFromProjectBB,
  removeGroupFromAllProjectsBB,
  addAgentIdsToProjectBB,
  removeAgentIdsFromProjectBB,
  removeAgentFromAllProjectsBB,
} = require('@librechat/api');

module.exports = {
  getProjectById: getProjectByIdBB,
  getProjectByName: getProjectByNameBB,
  addGroupIdsToProject: addGroupIdsToProjectBB,
  removeGroupIdsFromProject: removeGroupIdsFromProjectBB,
  removeGroupFromAllProjects: removeGroupFromAllProjectsBB,
  addAgentIdsToProject: addAgentIdsToProjectBB,
  removeAgentIdsFromProject: removeAgentIdsFromProjectBB,
  removeAgentFromAllProjects: removeAgentFromAllProjectsBB,
};
