// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

contract FLRegistry {
    struct ModelRound {
        uint256 roundNum;
        string modelHash;
        address author;
        uint256 timestamp;
    }

    mapping(uint256 => ModelRound) public history;
    mapping(uint256 => mapping(address => ModelRound)) public clientHistory;

    uint256 public latestRound;
    bool public hasModel;

    event ModelUpdated(uint256 round, string modelHash, address author);

    function registerClientModel(uint256 round, string memory hash) public {
        clientHistory[round][msg.sender] = ModelRound(round, hash, msg.sender, block.timestamp);
        emit ModelUpdated(round, hash, msg.sender);
    }

    function updateModel(uint256 round, string memory hash) public {
        history[round] = ModelRound(round, hash, msg.sender, block.timestamp);
        latestRound = round;
        hasModel = true;
        emit ModelUpdated(round, hash, msg.sender);
    }

    function getLastModel() public view returns (ModelRound memory) {
        require(hasModel, "No hay modelos registrados");
        return history[latestRound];
    }

    function getClientModel(uint256 round, address client) public view returns (string memory) {
        return clientHistory[round][client].modelHash;
    }
}