function toggleGoalState(switchElement, goalId) {
	const state = switchElement.checked;

	const data = {
		"goal_id": goalId,
		"state": state
	};

	fetch("/goals/toggle_goal_state", {
		method: "POST",
		headers: {
			"Content-Type": "application/json"
		},
		body: JSON.stringify(data)
	})
	.then(response => response.json())
	.then(data => {
		if (data["success"]) {
			console.log("Goal state toggled successfully");
		} else {
			console.error("Failed to toggle goal state");
		}
	})
	.catch((error) => {
		console.error("Failed to toggle goal state");
	});
}