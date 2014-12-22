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
	
	$('.click_edit_rule').click(function()
	{
		var parent = $(this).parent()

		$('#edit_perm_rid').attr('value',parent.data('rid'));
		$('#edit_perm_name').text(parent.data('name'));
		var src = parent.data('src');

		$('#edit_perm_src_0').removeAttr('selected');
		$('#edit_perm_src_1').removeAttr('selected');
		$('#edit_perm_src_2').removeAttr('selected');
		$('#edit_perm_src_' + src).attr('selected','selected');
		
		var web = parent.data('web');
		$('#edit_perm_web').prop('checked', web);
		var admin = parent.data('admin');
		$('#edit_perm_admin').prop('checked', admin);
		
		var source = parent.data('source');
		if (source == 'adgroup')
		{
			$('#admin_group_edit').addClass('hidden');
			$('#src_control_select_edit').addClass('hidden');
		}
		else
		{
			$('#admin_group_edit').removeClass('hidden');
			$('#src_control_select_edit').removeClass('hidden');

		}
		
		$('#edit_perm').modal({show: true});
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
	
	$(document).ready(function ()
	{
		$("[rel=tooltip]").tooltip();
	});
});
