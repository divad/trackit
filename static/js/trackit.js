$(document).ready(function() 
{
	$('.click_edit_member').click(function()
	{
		var parent = $(this).parent()

		$('#edit_member_form_username').attr('value',parent.data('username'));
		$('#edit_member_username').text(parent.data('username'));
		$('#edit_member_fullname').text(parent.data('fullname'));
		var admin = parent.data('admin');

		if (admin == 1)
		{
			$('#role_admin').attr('selected','selected');
			$('#role_member').removeAttr('selected');
		}
		else
		{
			$('#role_member').attr('selected','selected');
			$('#role_admin').removeAttr('selected');
		}
		
		$('#edit_member').modal({show: true});
		event.preventDefault();
		event.stopPropagation();
	});
});

$(document).ready(function($)
{
	$(".rowclick-td").click(function()
	{
		window.document.location = $(this).parent().data('url');
	});
	
	$(function()
	{
		$("#tsort").tablesorter();
	});
	
	$(document).ready(function ()
	{
		$("[rel=tooltip]").tooltip();
	});
});
